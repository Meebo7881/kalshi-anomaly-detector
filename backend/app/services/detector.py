from sqlalchemy.orm import Session
from app.models.models import Market, Trade, Baseline, Anomaly, TraderProfile
from datetime import datetime, timedelta
import numpy as np
from typing import Tuple, Dict, List, Optional


class AnomalyDetector:
    def __init__(self, db: Session):
        self.db = db

    # -------------------------------------------------------------------------
    # 1. BASELINE CALCULATION (unchanged)
    # -------------------------------------------------------------------------
    def calculate_baseline(self, ticker: str, window_days: int = 30) -> Optional[Baseline]:
        """Calculate rolling 30-day baseline statistics."""
        cutoff = datetime.utcnow() - timedelta(days=window_days)
        trades = (
            self.db.query(Trade)
            .filter(Trade.ticker == ticker, Trade.timestamp >= cutoff)
            .all()
        )

        if len(trades) < 10:
            return None

        volumes = [t.volume for t in trades]
        prices = [t.price for t in trades]

        baseline = self.db.query(Baseline).filter_by(ticker=ticker).first()
        if baseline:
            # Update existing
            baseline.avg_volume = float(np.mean(volumes))
            baseline.std_volume = float(np.std(volumes))
            baseline.avg_price = float(np.mean(prices))
            baseline.std_price = float(np.std(prices))
            baseline.avg_trades_per_hour = len(trades) / (window_days * 24)
            baseline.last_updated = datetime.utcnow()
        else:
            # Create new
            baseline = Baseline(
                ticker=ticker,
                avg_volume=float(np.mean(volumes)),
                std_volume=float(np.std(volumes)),
                avg_price=float(np.mean(prices)),
                std_price=float(np.std(prices)),
                avg_trades_per_hour=len(trades) / (window_days * 24),
                last_updated=datetime.utcnow(),
            )
            self.db.add(baseline)

        self.db.commit()
        return baseline

    # -------------------------------------------------------------------------
    # 2. VOLUME ANOMALY (unchanged)
    # -------------------------------------------------------------------------
    def detect_volume_anomaly(
        self, ticker: str, current_volume: float, threshold: float = 3.0
    ) -> Tuple[bool, float]:
        """Detect if current volume is anomalous (Z-score)."""
        baseline = self.db.query(Baseline).filter_by(ticker=ticker).first()
        if not baseline or baseline.std_volume == 0:
            return False, 0.0

        zscore = (current_volume - baseline.avg_volume) / baseline.std_volume
        return abs(zscore) >= threshold, zscore

    # -------------------------------------------------------------------------
    # 3. ORDER FLOW TOXICITY (VPIN) - NEW
    # -------------------------------------------------------------------------
    def calculate_vpin(self, ticker: str, window_trades: int = 50) -> float:
        """
        Calculate VPIN (Volume-synchronized Probability of Informed Trading).
        High VPIN = high order flow toxicity = more informed traders.
        Range: 0.0 (balanced) to 1.0 (max imbalance).
        """
        trades = (
            self.db.query(Trade)
            .filter(Trade.ticker == ticker)
            .order_by(Trade.timestamp.desc())
            .limit(window_trades)
            .all()
        )

        if len(trades) < 10:
            return 0.0

        # Classify trades as buy (yes/buy) or sell (no/sell)
        buy_volume = sum(t.volume for t in trades if t.side in ["yes", "buy"])
        sell_volume = sum(t.volume for t in trades if t.side in ["no", "sell"])
        total_volume = buy_volume + sell_volume

        if total_volume == 0:
            return 0.0

        # VPIN = absolute order imbalance / total volume
        vpin = abs(buy_volume - sell_volume) / total_volume
        return vpin

    # -------------------------------------------------------------------------
    # 4. WHALE WALLET DETECTION - NEW
    # -------------------------------------------------------------------------
    def detect_whale_trades(
        self, ticker: str, threshold_usd: float = 5000.0, lookback_hours: int = 24
    ) -> List[Dict]:
        """
        Flag abnormally large trades (whales).
        Returns list of whale trades with trader_id, value, timestamp.
        """
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
        recent_trades = (
            self.db.query(Trade)
            .filter(Trade.ticker == ticker, Trade.timestamp >= cutoff)
            .all()
        )

        whales = []
        for trade in recent_trades:
            # Estimate USD value (volume * price; assumes price is 0-1 and volume is contract count)
            # For real USD, multiply by contract value (e.g., $1/contract on Kalshi)
            trade_value = trade.volume * trade.price
            if trade_value >= threshold_usd:
                whales.append(
                    {
                        "trade_id": trade.trade_id,
                        "trader_id": trade.trader_id,
                        "value_usd": trade_value,
                        "timestamp": trade.timestamp.isoformat(),
                    }
                )

        return whales

    def update_trader_profiles(self):
        """Maintain trader profiles to identify new/suspicious wallets."""
        # Get all recent trades
        cutoff = datetime.utcnow() - timedelta(days=7)
        trades = self.db.query(Trade).filter(Trade.timestamp >= cutoff).all()

        trader_stats = {}
        for t in trades:
            if not t.trader_id:
                continue
            if t.trader_id not in trader_stats:
                trader_stats[t.trader_id] = {
                    "first_seen": t.timestamp,
                    "total_trades": 0,
                    "total_volume_usd": 0.0,
                }
            trader_stats[t.trader_id]["total_trades"] += 1
            trader_stats[t.trader_id]["total_volume_usd"] += t.volume * t.price
            if t.timestamp < trader_stats[t.trader_id]["first_seen"]:
                trader_stats[t.trader_id]["first_seen"] = t.timestamp

        # Update profiles
        for trader_id, stats in trader_stats.items():
            profile = (
                self.db.query(TraderProfile).filter_by(trader_id=trader_id).first()
            )
            if not profile:
                profile = TraderProfile(
                    trader_id=trader_id,
                    first_seen=stats["first_seen"],
                    total_trades=stats["total_trades"],
                    total_volume_usd=stats["total_volume_usd"],
                    avg_trade_size_usd=stats["total_volume_usd"] / stats["total_trades"],
                    is_whale=stats["total_volume_usd"] > 50000,  # Threshold for whale
                    last_updated=datetime.utcnow(),
                )
                self.db.add(profile)
            else:
                profile.total_trades = stats["total_trades"]
                profile.total_volume_usd = stats["total_volume_usd"]
                profile.avg_trade_size_usd = (
                    stats["total_volume_usd"] / stats["total_trades"]
                )
                profile.is_whale = stats["total_volume_usd"] > 50000
                profile.last_updated = datetime.utcnow()

        self.db.commit()

    # -------------------------------------------------------------------------
    # 5. PRICE + VOLUME SPIKE CORRELATION - NEW
    # -------------------------------------------------------------------------
    def detect_price_volume_correlation(self, ticker: str, lookback_hours: int = 1) -> Tuple[bool, float]:
        """
        Detect coordinated price jump + volume surge (front-running signal).
        Returns (is_suspicious, correlation_score).
        """
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
        trades = (
            self.db.query(Trade)
            .filter(Trade.ticker == ticker, Trade.timestamp >= cutoff)
            .order_by(Trade.timestamp)
            .all()
        )

        if len(trades) < 5:
            return False, 0.0

        # Calculate price change
        first_price = trades[0].price
        last_price = trades[-1].price
        if first_price == 0:
            return False, 0.0
        price_change = abs(last_price - first_price) / first_price

        # Calculate volume surge
        total_volume = sum(t.volume for t in trades)
        baseline = self.db.query(Baseline).filter_by(ticker=ticker).first()

        if not baseline or baseline.avg_volume == 0:
            return False, 0.0

        volume_ratio = total_volume / baseline.avg_volume

        # Flag if both price moved >10% AND volume >3x normal
        is_suspicious = price_change > 0.10 and volume_ratio > 3.0
        correlation_score = price_change * volume_ratio * 10  # Scale for scoring

        return is_suspicious, correlation_score

    # -------------------------------------------------------------------------
    # 6. AGGRESSIVE TIME-TO-RESOLUTION URGENCY - UPDATED
    # -------------------------------------------------------------------------
    def calculate_urgency_score(self, days_to_close: int) -> float:
        """
        More aggressive urgency scoring.
        Markets close to resolution get much higher weights.
        """
        if days_to_close <= 0:
            return 4.0  # Already closed or closing today
        elif days_to_close <= 1:
            return 3.5
        elif days_to_close <= 2:
            return 3.0
        elif days_to_close <= 3:
            return 2.5
        elif days_to_close <= 7:
            return 2.0
        elif days_to_close <= 14:
            return 1.0
        else:
            return 0.0

    # -------------------------------------------------------------------------
    # 7. COMPOSITE ANOMALY SCORE - UPDATED
    # -------------------------------------------------------------------------
    def calculate_anomaly_score(
        self,
        volume_zscore: float,
        price_car: float,
        days_to_close: int,
        vpin: float,
        price_volume_corr: float,
        whale_count: int,
    ) -> float:
        """
        Calculate composite anomaly score (0-10+).
        Higher = more likely insider trading.
        """
        # Volume component (0-5)
        volume_score = min(abs(volume_zscore) / 2, 5.0)

        # Price CAR component (0-3) - currently unused; wire up when you have price model
        price_score = min(abs(price_car) / 2, 3.0)

        # Urgency (0-4) - aggressive weighting
        urgency_score = self.calculate_urgency_score(days_to_close)

        # VPIN toxicity (0-3)
        toxicity_score = min(vpin * 3, 3.0)

        # Price-volume correlation (0-3)
        corr_score = min(price_volume_corr, 3.0)

        # Whale presence (0-2)
        whale_score = min(whale_count * 0.5, 2.0)

        total = (
            volume_score
            + price_score
            + urgency_score
            + toxicity_score
            + corr_score
            + whale_score
        )
        return min(total, 10.0)

    # -------------------------------------------------------------------------
    # 8. LOG ANOMALY - UPDATED
    # -------------------------------------------------------------------------
    def log_anomaly(
        self,
        ticker: str,
        anomaly_type: str,
        score: float,
        details: Dict,
    ):
        """Log detected anomaly with enhanced details."""
        if score >= 8.0:
            severity = "critical"
        elif score >= 7.0:
            severity = "high"
        elif score >= 5.0:
            severity = "medium"
        else:
            severity = "low"

        anomaly = Anomaly(
            ticker=ticker,
            anomaly_type=anomaly_type,
            score=score,
            severity=severity,
            details=details,
            detected_at=datetime.utcnow(),
        )
        self.db.add(anomaly)
        self.db.commit()
