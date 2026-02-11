from sqlalchemy.orm import Session
from app.models.models import Trade, MarketBaseline, Anomaly
from datetime import datetime, timedelta
import numpy as np

class AnomalyDetector:
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_baseline(self, ticker: str, window_days: int = 30):
        """Calculate baseline statistics for a market."""
        cutoff = datetime.utcnow() - timedelta(days=window_days)
        
        trades = self.db.query(Trade).filter(
            Trade.ticker == ticker,
            Trade.timestamp >= cutoff
        ).all()
        
        if len(trades) < 10:
            return None
        
        volumes = [t.volume for t in trades]
        prices = [t.price for t in trades]
        
        # Check if baseline exists
        baseline = self.db.query(MarketBaseline).filter_by(ticker=ticker).first()
        
        if baseline:
            # Update existing
            baseline.avg_volume = float(np.mean(volumes))
            baseline.std_volume = float(np.std(volumes))
            baseline.avg_price = float(np.mean(prices))
            baseline.std_price = float(np.std(prices))
            baseline.last_updated = datetime.utcnow()
        else:
            # Create new
            baseline = MarketBaseline(
                ticker=ticker,
                avg_volume=float(np.mean(volumes)),
                std_volume=float(np.std(volumes)),
                avg_price=float(np.mean(prices)),
                std_price=float(np.std(prices)),
                avg_trades_per_hour=len(trades) / (window_days * 24),
                last_updated=datetime.utcnow()
            )
            self.db.add(baseline)
        
        self.db.commit()
        return baseline
    
    def detect_volume_anomaly(self, ticker: str, current_volume: float, threshold: float = 3.0):
        """Detect if current volume is anomalous."""
        baseline = self.db.query(MarketBaseline).filter_by(ticker=ticker).first()
        
        if not baseline or baseline.std_volume == 0:
            return False, 0
        
        z_score = (current_volume - baseline.avg_volume) / baseline.std_volume
        
        return abs(z_score) > threshold, z_score
    
    def calculate_anomaly_score(self, volume_zscore: float, price_car: float, 
                               days_to_close: int, orderbook_imbalance: float) -> float:
        """Calculate composite anomaly score (0-10)."""
        volume_score = min(abs(volume_zscore) / 2, 5)
        price_score = min(abs(price_car) / 2, 3)
        urgency_score = max(0, 2 - (days_to_close / 15))
        imbalance_score = min(abs(orderbook_imbalance) * 2, 2)
        
        return volume_score + price_score + urgency_score + imbalance_score
    
    def log_anomaly(self, ticker: str, anomaly_type: str, score: float, details: dict):
        """Log detected anomaly."""
        severity = "high" if score >= 7.5 else "medium" if score >= 5.0 else "low"
        
        anomaly = Anomaly(
            ticker=ticker,
            anomaly_type=anomaly_type,
            score=score,
            severity=severity,
            details=details,
            detected_at=datetime.utcnow()
        )
        
        self.db.add(anomaly)
        self.db.commit()
