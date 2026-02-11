from celery import Celery
from app.core.config import settings
from app.services.kalshi_service import KalshiAPI
from app.services.detector import AnomalyDetector
from app.models.models import Trade, Market
from app.core.database import SessionLocal
from datetime import datetime, timedelta
import asyncio

celery_app = Celery('tasks', broker=settings.REDIS_URL)

@celery_app.task
def update_market_data():
    db = SessionLocal()
    kalshi = KalshiAPI(settings.KALSHI_API_KEY_ID, settings.KALSHI_PRIVATE_KEY_PATH)
    
    try:
        print("📊 Fetching markets from Kalshi...")
        markets = asyncio.run(kalshi.get_markets(status="open"))
        print(f"✅ Fetched {len(markets)} markets")
        
        # Process first 10 markets for testing
        for market in markets[:10]:
            ticker = market["ticker"]
            
            # Save or update market
            db_market = db.query(Market).filter_by(ticker=ticker).first()
            if not db_market:
                db_market = Market(
                    ticker=ticker,
                    title=market["title"],
                    category=market.get("category"),
                    close_date=datetime.fromisoformat(market["close_time"].replace('Z', '+00:00'))
                )
                db.add(db_market)
                print(f"  • Added market: {ticker}")
            
            # Fetch trades for this market
            try:
                trades_data = asyncio.run(kalshi.get_trades(ticker))
                print(f"  • Fetched {len(trades_data)} trades for {ticker}")
                
                if trades_data:
                    for trade in trades_data:
                        try:
                            # Parse timestamp (handle both seconds and milliseconds)
                            created_time = trade.get("created_time", trade.get("ts", 0))
                            if created_time > 9999999999:  # Milliseconds
                                timestamp = datetime.fromtimestamp(created_time / 1000)
                            else:  # Seconds
                                timestamp = datetime.fromtimestamp(created_time)
                            
                            # Create trade record with flexible field handling
                            db_trade = Trade(
                                ticker=ticker,
                                trade_id=str(trade.get("trade_id", trade.get("id", f"{ticker}_{created_time}"))),
                                price=float(trade.get("yes_price", trade.get("price", 0))),
                                volume=int(trade.get("count", trade.get("volume", trade.get("size", 1)))),
                                side=trade.get("side", trade.get("taker_side", "unknown")),
                                timestamp=timestamp
                            )
                            db.merge(db_trade)
                            
                        except Exception as e:
                            print(f"    ⚠️  Error parsing trade: {e}")
                            print(f"    Trade data: {trade}")
                            continue
                    
                    print(f"  ✅ Stored {len(trades_data)} trades for {ticker}")
                    
            except Exception as e:
                print(f"  ⚠️  Error fetching trades for {ticker}: {e}")
                continue
        
        db.commit()
        print("✅ Market data update complete!")
        
    except Exception as e:
        print(f"❌ Error in update_market_data: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

@celery_app.task
def run_anomaly_detection():
    db = SessionLocal()
    detector = AnomalyDetector(db)
    
    try:
        print("🔍 Running anomaly detection...")
        markets = db.query(Market).filter_by(status="active").all()
        print(f"  Analyzing {len(markets)} markets")
        
        anomalies_found = 0
        
        for market in markets:
            # Calculate baseline
            baseline = detector.calculate_baseline(market.ticker)
            if not baseline:
                continue
            
            # Get recent trades
            recent_trades = db.query(Trade).filter(
                Trade.ticker == market.ticker,
                Trade.timestamp >= datetime.utcnow() - timedelta(hours=1)
            ).all()
            
            if not recent_trades:
                continue
            
            total_volume = sum(t.volume for t in recent_trades)
            
            # Check for volume anomaly
            is_anomaly, z_score = detector.detect_volume_anomaly(market.ticker, total_volume)
            
            if is_anomaly:
                days_to_close = (market.close_date - datetime.utcnow()).days if market.close_date else 999
                score = detector.calculate_anomaly_score(
                    volume_zscore=z_score,
                    price_car=0,
                    days_to_close=days_to_close,
                    orderbook_imbalance=0
                )
                
                print(f"  🚨 Anomaly detected in {market.ticker}! Score: {score:.2f}, Z-score: {z_score:.2f}")
                
                detector.log_anomaly(
                    ticker=market.ticker,
                    anomaly_type="volume",
                    score=score,
                    details={
                        "z_score": float(z_score),
                        "volume": total_volume,
                        "days_to_close": days_to_close,
                        "baseline_avg": float(baseline.avg_volume)
                    }
                )
                anomalies_found += 1
        
        print(f"✅ Anomaly detection complete! Found {anomalies_found} anomalies")
        
    except Exception as e:
        print(f"❌ Error in anomaly detection: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

celery_app.conf.beat_schedule = {
    'update-data-every-5-minutes': {
        'task': 'app.tasks.monitor.update_market_data',
        'schedule': 300.0,
    },
    'run-detection-every-5-minutes': {
        'task': 'app.tasks.monitor.run_anomaly_detection',
        'schedule': 300.0,
    },
}
