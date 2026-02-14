import asyncio
from datetime import datetime, timedelta, timezone
from typing import List

from celery import Celery
from celery.utils.log import get_task_logger
from sqlalchemy.dialects.postgresql import insert

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.models import Market, Trade, Baseline, Anomaly, TraderProfile
from app.services.kalshi_service import KalshiAPI
from app.services.detector import AnomalyDetector

logger = get_task_logger(__name__)

celery_app = Celery("kalshi_anomaly_detector")
celery_app.conf.broker_url = settings.REDIS_URL
celery_app.conf.result_backend = settings.REDIS_URL


@celery_app.task(bind=True, max_retries=3)
def update_market_data(self):
    """Update market data with better error handling and batch commits."""
    db = SessionLocal()
    kalshi = KalshiAPI(
        api_key_id=settings.KALSHI_API_KEY_ID,
        private_key_path=settings.KALSHI_PRIVATE_KEY_PATH,
        max_rps=8.0,
        redis_url=settings.REDIS_URL,
    )

    start_time = datetime.now(timezone.utc)
    trades_inserted = 0
    error_count = 0

    try:
        logger.info("Starting market data update")

        # Get markets
        markets = asyncio.run(
            kalshi.get_all_markets_from_events(
                categories=settings.MONITORED_CATEGORIES,
                max_events=100,
            )
        )

        if not markets:
            logger.warning("No markets found from events, fetching open markets")
            markets = asyncio.run(
                kalshi.get_markets(status="open", limit=200)
            )

        if not markets:
            logger.warning("No markets to process")
            return

        logger.info(f"Found {len(markets)} markets to process")

        # Upsert markets in batch
        market_data = []
        for m in markets:
            try:
                close_time = None
                if m.get("close_time"):
                    # Kalshi uses ISO 8601 with Z
                    close_time = datetime.fromisoformat(
                        m["close_time"].replace("Z", "+00:00")
                    )

                market_data.append(
                    {
                        "ticker": m["ticker"],
                        "title": m.get("title", ""),
                        "category": m.get("category", "Unknown"),
                        "status": m.get("status", "unknown"),
                        "close_date": close_time,
                    }
                )
            except Exception as e:
                logger.error(f"Error parsing market {m.get('ticker')}: {e}", exc_info=True)
                continue

        if market_data:
            stmt = insert(Market).values(market_data)
            stmt = stmt.on_conflict_do_update(
                index_elements=[Market.ticker],
                set_={
                    "title": stmt.excluded.title,
                    "category": stmt.excluded.category,
                    "status": stmt.excluded.status,
                    "close_date": stmt.excluded.close_date,
                },
            )
            db.execute(stmt)
            db.commit()

        # Process trades in batches
        for i, market in enumerate(markets):
            ticker = market["ticker"]

            if i % 20 == 0:
                logger.info(f"Progress {i}/{len(markets)} markets")

            try:
                trades_data = asyncio.run(kalshi.get_trades(ticker))
                if not trades_data:
                    continue

                trade_batch = []
                for trade in trades_data:
                    try:
                        created_time = trade.get("created_time") or trade.get("ts")

                        if isinstance(created_time, str):
                            # ISO 8601 string
                            timestamp = datetime.fromisoformat(
                                created_time.replace("Z", "+00:00")
                            )
                        else:
                            # Fallback for epoch ms/s
                            if created_time > 9_999_999_999:
                                # ms
                                timestamp = datetime.fromtimestamp(
                                    created_time / 1000.0, tz=timezone.utc
                                )
                            else:
                                timestamp = datetime.fromtimestamp(
                                    created_time, tz=timezone.utc
                                )

                        trade_batch.append(
                            {
                                "ticker": ticker,
                                "trade_id": str(trade.get("trade_id")),
                                "price": float(
                                    trade.get("yes_price")
                                    or trade.get("price")
                                    or 0
                                ),
                                "volume": int(trade.get("count") or 1),
                                "side": trade.get("taker_side")
                                or trade.get("side")
                                or "unknown",
                                "timestamp": timestamp,
                                "trader_id": trade.get("trader_id"),
                            }
                        )
                    except Exception as e:
                        logger.error(f"Parse error for trade in {ticker}: {e}", exc_info=True)
                        error_count += 1

                if trade_batch:
                    stmt = insert(Trade).values(trade_batch)
                    stmt = stmt.on_conflict_do_nothing(index_elements=[Trade.trade_id])
                    result = db.execute(stmt)
                    trades_inserted += result.rowcount
                    db.commit()

            except Exception as e:
                logger.error(f"Error fetching trades for {ticker}: {e}", exc_info=True)
                error_count += 1
                if error_count > 20:
                    logger.error("Too many trade fetch errors, aborting")
                    break

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(
            f"✅ Complete in {elapsed:.1f}s: {trades_inserted} trades, {error_count} errors"
        )

    except Exception as e:
        logger.error(f"Critical error in update_market_data: {e}", exc_info=True)
        db.rollback()
        raise self.retry(exc=e, countdown=60, max_retries=3)
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def run_anomaly_detection(self):
    """Run anomaly detection with deduplication and alerting."""
    db = SessionLocal()
    detector = AnomalyDetector(db)
    start_time = datetime.now(timezone.utc)

    anomalies_found = 0
    critical_anomalies: List[Anomaly] = []

    try:
        logger.info("Starting anomaly detection")

        markets = db.query(Market).filter_by(status="active").all()

        for market in markets:
            try:
                baseline = detector.calculate_baseline(market.ticker)
                if not baseline:
                    continue

                # Last 1 hour trades
                recent_trades = (
                    db.query(Trade)
                    .filter(
                        Trade.ticker == market.ticker,
                        Trade.timestamp
                        >= datetime.utcnow() - timedelta(hours=1),
                    )
                    .all()
                )
                if not recent_trades:
                    continue

                total_volume = sum(t.volume for t in recent_trades)
                is_anomaly, z_score = detector.detect_volume_anomaly(
                    market.ticker, total_volume
                )
                if not is_anomaly:
                    continue

                # Calculate metrics
                vpin = detector.calculate_vpin(market.ticker)
                whales = detector.detect_whale_trades(
                    market.ticker, threshold_usd=None
                )
                is_corr, corr_score = detector.detect_price_volume_correlation(
                    market.ticker
                )

                days_to_close = (
                    (market.close_date - datetime.utcnow()).days
                    if market.close_date
                    else 999
                )

                score = detector.calculate_anomaly_score(
                    volume_zscore=z_score,
                    price_car=0,
                    days_to_close=days_to_close,
                    vpin=vpin,
                    price_volume_corr=corr_score,
                    whale_count=len(whales),
                )

                details = {
                    "zscore": float(z_score),
                    "volume": total_volume,
                    "vpin": float(vpin),
                    "whale_count": len(whales),
                    "whale_details": whales[:5],
                    "price_volume_corr": float(corr_score),
                    "days_to_close": days_to_close,
                }

                anomaly = detector.log_anomaly(
                    ticker=market.ticker,
                    anomaly_type="volume",
                    score=score,
                    details=details,
                )

                anomalies_found += 1
                if anomaly.severity == "critical":
                    critical_anomalies.append(anomaly)

            except Exception as e:
                logger.error(
                    f"Detection error for {market.ticker}: {e}", exc_info=True
                )
                continue

        # Send alerts for critical anomalies (stub)
        if critical_anomalies:
            logger.info(
                f"Detection complete! {len(critical_anomalies)} critical alerts"
            )
        else:
            logger.info(f"Detection complete! {anomalies_found} anomalies found, 0 critical")

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
        logger.info(f"✅ Anomaly detection complete in {elapsed:.1f}s")

    except Exception as e:
        logger.error(f"Error in anomaly detection: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60, max_retries=3)
    finally:
        db.close()


@celery_app.task
def send_anomaly_alerts(anomaly_ids: List[int]):
    """Send notifications for critical anomalies (placeholder)."""
    db = SessionLocal()
    try:
        anomalies = (
            db.query(Anomaly).filter(Anomaly.id.in_(anomaly_ids)).all()
        )
        for anomaly in anomalies:
            logger.critical(
                f"CRITICAL {anomaly.ticker} score {anomaly.score:.2f}"
            )
            # TODO: Implement Slack/email/webhook notifications here
    finally:
        db.close()
