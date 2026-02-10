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
    kalshi = KalshiAPI(settings.KALSHI_API_KEY, settings.KALSHI_API_SECRET)
    
    try:
        markets = asyncio.run(kalshi.get_markets(status="open"))
        
        for market in markets:
            ticker = market["ticker"]
            
            db_market = db.query(Market).filter_by(ticker=ticker).first()
            if not db_market:
                db_market = Market(
                    ticker=ticker,
                    title=market["title"],
                    category=market.get("category"),
                    close_date=datetime.fromisoformat(market["close_time"].replace('Z', '+00:00'))
                )
                db.add(db_market)
            
            trades = asyncio.run(kalshi.get_trades(ticker))
            
            for trade in trades:
                db_trade = Trade(
                    ticker=ticker,
                    trade_id=trade["trade_id"],
                    price=trade["yes_price"],
                    volume=trade["count"],
                    side=trade["side"],
                    timestamp=datetime.fromtimestamp(trade["created_time"])
                )
                db.merge(db_trade)
        
        db.commit()
    finally:
        db.close()

@celery_app.task
def run_anomaly_detection():
    db = SessionLocal()
    detector = AnomalyDetector(db)
    
    try:
        markets = db.query(Market).filter_by(status="active").all()
        
        for market in markets:
            detector.calculate_baseline(market.ticker)
            
            recent_trades = db.query(Trade).filter(
                Trade.ticker == market.ticker,
                Trade.timestamp >= datetime.utcnow() - timedelta(hours=1)
            ).all()
            
            total_volume = sum(t.volume for t in recent_trades)
            
            is_anomaly, z_score = detector.detect_volume_anomaly(market.ticker, total_volume)
            
            if is_anomaly:
                days_to_close = (market.close_date - datetime.utcnow()).days
                score = detector.calculate_anomaly_score(
                    volume_zscore=z_score,
                    price_car=0,
                    days_to_close=days_to_close,
                    orderbook_imbalance=0
                )
                
                detector.log_anomaly(
                    ticker=market.ticker,
                    anomaly_type="volume",
                    score=score,
                    details={
                        "z_score": z_score,
                        "volume": total_volume,
                        "days_to_close": days_to_close
                    }
                )
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
