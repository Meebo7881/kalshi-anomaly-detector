import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Tuple, List
from sqlalchemy.orm import Session
from app.models.models import Trade, MarketBaseline, Anomaly
from app.core.config import settings

class AnomalyDetector:
    
    def __init__(self, db: Session):
        self.db = db
        
    def calculate_baseline(self, ticker: str) -> MarketBaseline:
        cutoff_date = datetime.utcnow() - timedelta(days=settings.BASELINE_WINDOW_DAYS)
        
        trades = self.db.query(Trade).filter(
            Trade.ticker == ticker,
            Trade.timestamp >= cutoff_date
        ).all()
        
        if len(trades) < 10:
            return None
        
        volumes = [t.volume for t in trades]
        prices = [t.price for t in trades]
        
        baseline = MarketBaseline(
            ticker=ticker,
            avg_volume=np.mean(volumes),
            std_volume=np.std(volumes),
            avg_price=np.mean(prices),
            std_price=np.std(prices),
            avg_trades_per_hour=len(trades) / (settings.BASELINE_WINDOW_DAYS * 24),
            last_updated=datetime.utcnow()
        )
        
        self.db.merge(baseline)
        self.db.commit()
        return baseline
    
    def detect_volume_anomaly(self, ticker: str, current_volume: int) -> Tuple[bool, float]:
        baseline = self.db.query(MarketBaseline).filter_by(ticker=ticker).first()
        
        if not baseline or baseline.std_volume == 0:
            return False, 0.0
        
        z_score = (current_volume - baseline.avg_volume) / baseline.std_volume
        is_anomaly = z_score > settings.VOLUME_THRESHOLD
        return is_anomaly, float(z_score)
    
    def detect_price_anomaly(self, ticker: str, price_changes: List[float]) -> Tuple[bool, float]:
        if len(price_changes) < 2:
            return False, 0.0
        
        car = sum(price_changes)
        is_anomaly = abs(car) > settings.PRICE_THRESHOLD
        return is_anomaly, abs(car)
    
    def calculate_anomaly_score(self, volume_zscore: float, price_car: float,
                                days_to_close: int, orderbook_imbalance: float) -> float:
        volume_score = min(volume_zscore / 5.0, 1.0) * 4.0
        price_score = min(price_car / 10.0, 1.0) * 3.0
        timing_score = max(0, (10 - days_to_close) / 10) * 2.0
        imbalance_score = min(orderbook_imbalance, 1.0) * 1.0
        
        total_score = volume_score + price_score + timing_score + imbalance_score
        return round(total_score, 2)
    
    def classify_severity(self, score: float) -> str:
        if score >= settings.HIGH_ALERT_SCORE:
            return "high"
        elif score >= settings.MEDIUM_ALERT_SCORE:
            return "medium"
        else:
            return "low"
    
    def log_anomaly(self, ticker: str, anomaly_type: str, score: float, details: Dict):
        anomaly = Anomaly(
            ticker=ticker,
            anomaly_type=anomaly_type,
            score=score,
            severity=self.classify_severity(score),
            details=details,
            detected_at=datetime.utcnow()
        )
        self.db.add(anomaly)
        self.db.commit()
