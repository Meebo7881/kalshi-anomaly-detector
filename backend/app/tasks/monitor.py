from celery import Celery
from celery.utils.log import get_task_logger
from typing import Dict, List
from app.core.config import settings
from app.services.kalshi_service import KalshiAPI
from app.services.detector import AnomalyDetector
from app.models.models import Trade, Market, Anomaly
from app.core.database import SessionLocal
from datetime import datetime, timedelta, timezone
from sqlalchemy.dialects.postgresql import insert
import asyncio

celery_app = Celery('tasks', broker=settings.REDIS_URL)

logger = get_task_logger(__name__)

MONITORED_CATEGORIES = ['Politics', 'Entertainment', 'Economics', 'World', 'Elections']

def parse_trade(trade_data: Dict, ticker: str) -> Dict:
    """Parse trade data from Kalshi API response."""
    created_time = trade_data.get("created_time", trade_data.get("ts", ""))
    
    # Handle ISO 8601 string format (e.g., "2026-02-12T02:15:52.191054Z")
    if isinstance(created_time, str):
        timestamp = datetime.fromisoformat(created_time.replace('Z', '+00:00'))
    elif created_time > 9999999999:
        timestamp = datetime.fromtimestamp(created_time / 1000, tz=timezone.utc)
    else:
        timestamp = datetime.fromtimestamp(created_time, tz=timezone.utc)

    return {
        "ticker": ticker,
        "trade_id": str(trade_data.get("trade_id", f"{ticker}_{created_time}")),
        "price": float(trade_data.get("yes_price", trade_data.get("price", 0))),
        "volume": int(trade_data.get("count", 1)),
        "side": trade_data.get("taker_side", trade_data.get("side", "unknown")),  # Fix: taker_side first
        "timestamp": timestamp,
        "trader_id": trade_data.get("trader_id")
    }


@celery_app.task(bind=True, max_retries=3)
def update_market_data(self):
    '''
    Update market data with BATCH OPERATIONS.

    BEFORE: 100+ individual commits
    AFTER: 2 batch commits (markets + trades)
    '''
    db = SessionLocal()
    kalshi = KalshiAPI(
    api_key_id=settings.KALSHI_API_KEY_ID,
    private_key_path=settings.KALSHI_PRIVATE_KEY_PATH,
    max_rps=8.0,
    redis_url=settings.REDIS_URL
)

    start_time = datetime.utcnow()

    try:
        logger.info("📊 Starting market data update")

        # Fetch markets
        markets = asyncio.run(kalshi.get_all_markets_from_events(
            categories=MONITORED_CATEGORIES,
            max_events=100,
            max_concurrent=1
        ))

        if not markets:
            markets = asyncio.run(kalshi.get_markets(status="open", limit=200))

        logger.info(f"✅ Found {len(markets)} markets")

        # BATCH INSERT 1: Markets
        market_data = []
        for m in markets:
            try:
                market_data.append({
                    "ticker": m["ticker"],
                    "title": m["title"],
                    "category": m.get("category"),
                    "close_date": datetime.fromisoformat(m["close_time"].replace('Z', '+00:00')),
                    "status": "active"
                })
            except Exception as e:
                logger.error(f"Error parsing market: {e}")

        if market_data:
            stmt = insert(Market).values(market_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=['ticker'],
                set_={
                    "title": stmt.excluded.title,
                    "category": stmt.excluded.category,
                    "status": stmt.excluded.status
                }
            )
            db.execute(stmt)
            db.commit()
            logger.info(f"✅ Upserted {len(market_data)} markets")

        # BATCH INSERT 2: Trades
        trades_inserted = 0
        error_count = 0

        for i, market in enumerate(markets):
            ticker = market["ticker"]

            if i > 0 and i % 20 == 0:
                logger.info(f"   Progress: {i}/{len(markets)} markets")

            try:
                trades_data = asyncio.run(kalshi.get_trades(ticker))
                if not trades_data:
                    continue

                trade_batch = []
                for trade in trades_data:
                    try:
                        trade_batch.append(parse_trade(trade, ticker))
                    except Exception as e:
                        error_count += 1

                if trade_batch:
                    stmt = insert(Trade).values(trade_batch)
                    stmt = stmt.on_conflict_do_nothing(index_elements=['trade_id'])
                    result = db.execute(stmt)
                    trades_inserted += result.rowcount
                    db.commit()

            except Exception as e:
                logger.error(f"Error fetching trades for {ticker}: {e}")
                error_count += 1
                if error_count >= 20:
                    break

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"✅ Complete in {elapsed:.1f}s: {trades_inserted} trades, {error_count} errors")

    except Exception as e:
        logger.error(f"❌ Critical error: {e}", exc_info=True)
        db.rollback()
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
    finally:
        db.close()

@celery_app.task(bind=True)
def run_anomaly_detection(self):
    '''Run anomaly detection with deduplication and alerting.'''
    db = SessionLocal()
    detector = AnomalyDetector(db)
    start_time = datetime.utcnow()

    try:
        logger.info("🔍 Starting anomaly detection")
        markets = db.query(Market).filter_by(status="active").all()

        anomalies_found = 0
        critical_anomalies = []

        for market in markets:
            try:
                baseline = detector.calculate_baseline(market.ticker)
                if not baseline:
                    continue

                recent_trades = db.query(Trade).filter(
                    Trade.ticker == market.ticker,
                    Trade.timestamp >= datetime.utcnow() - timedelta(hours=1)
                ).all()

                if not recent_trades:
                    continue

                total_volume = sum(t.volume for t in recent_trades)
                is_anomaly, z_score = detector.detect_volume_anomaly(market.ticker, total_volume)

                if not is_anomaly:
                    continue

                # Calculate metrics
                vpin = detector.calculate_vpin(market.ticker)
                whales = detector.detect_whale_trades(market.ticker, threshold_usd=2000)
                is_corr, corr_score = detector.detect_price_volume_correlation(market.ticker)

                days_to_close = (market.close_date - datetime.utcnow()).days if market.close_date else 999

                score = detector.calculate_anomaly_score(
                    volume_zscore=z_score,
                    price_car=0,
                    days_to_close=days_to_close,
                    vpin=vpin,
                    price_volume_corr=corr_score,
                    whale_count=len(whales)
                )

                # Log with deduplication
                anomaly = detector.log_anomaly(
                    ticker=market.ticker,
                    anomaly_type="volume",
                    score=score,
                    details={
                        "zscore": float(z_score),
                        "volume": total_volume,
                        "vpin": float(vpin),
                        "whale_trades": len(whales),
                        "whale_details": whales[:5],
                        "price_volume_corr": float(corr_score),
                        "days_to_close": days_to_close
                    }
                )

                anomalies_found += 1
                if anomaly.severity == "critical":
                    critical_anomalies.append(anomaly)

            except Exception as e:
                logger.error(f"Detection error for {market.ticker}: {e}")

        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"✅ Complete in {elapsed:.1f}s: {anomalies_found} found, {len(critical_anomalies)} critical")

        if critical_anomalies:
            send_critical_alerts.delay([a.id for a in critical_anomalies])

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
    finally:
        db.close()

@celery_app.task
def send_critical_alerts(anomaly_ids: List[int]):
    '''Send notifications for critical anomalies.'''
    db = SessionLocal()
    try:
        anomalies = db.query(Anomaly).filter(Anomaly.id.in_(anomaly_ids)).all()
        for anomaly in anomalies:
            logger.critical(f"🚨 CRITICAL: {anomaly.ticker} (score: {anomaly.score:.2f})")
            # TODO: Implement Slack/email notifications
    finally:
        db.close()

# Celery Beat schedule
celery_app.conf.beat_schedule = {
    'update-markets': {
        'task': 'app.tasks.monitor.update_market_data',
        'schedule': float(settings.UPDATE_INTERVAL_SECONDS or 300),
    },
    'detect-anomalies': {
        'task': 'app.tasks.monitor.run_anomaly_detection',
        'schedule': float(settings.DETECTION_INTERVAL_SECONDS or 300),
    },
}
