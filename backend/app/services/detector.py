from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models.models import Anomaly, Baseline, Market, Trade, TraderProfile


@dataclass
class BaselineStats:
    ticker: str
    avg_volume: float
    std_volume: float
    avg_price: float
    std_price: float
    avg_trades_per_hour: float
    last_updated: datetime


class AnomalyDetector:
    def __init__(self, db: Session, redis_client=None) -> None:
        self.db = db
        self.redis = redis_client

        # Centralized thresholds/config
        self.config: Dict[str, float] = {
            "volume_zscore_threshold": 3.0,
            "vpin_window_trades": 50,
            "whale_threshold_usd": 3000.0,        # lowered from 5000
            "soft_whale_threshold_usd": 1000.0,   # softer whale tier
            "price_change_threshold": 0.10,
            "volume_surge_multiplier": 3.0,
            "baseline_cache_ttl": 300,  # 5 minutes
        }

    # -------------------------------------------------------------------------
    # BASELINE CALCULATION
    # -------------------------------------------------------------------------

    def calculate_baseline(self, ticker: str, window_days: int = 30) -> Optional[BaselineStats]:
        """Calculate rolling 30-day baseline statistics for a market."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)

        trades = (
            self.db.query(Trade)
            .filter(Trade.ticker == ticker, Trade.timestamp >= cutoff)
            .all()
        )
        if len(trades) < 10:
            return None

        volumes = [t.volume for t in trades]
        prices = [t.price for t in trades]

        # Use numpy for robust stats
        avg_volume = float(np.mean(volumes))
        std_volume = float(np.std(volumes) or 0.0)
        avg_price = float(np.mean(prices))
        std_price = float(np.std(prices) or 0.0)

        # Approximate trades per hour over the window
        total_hours = window_days * 24
        avg_trades_per_hour = float(len(trades) / total_hours)

        # Upsert into Baseline table
        baseline = (
            self.db.query(Baseline)
            .filter_by(ticker=ticker)
            .first()
        )

        now = datetime.now(timezone.utc)

        if baseline:
            baseline.avg_volume = avg_volume
            baseline.std_volume = std_volume
            baseline.avg_price = avg_price
            baseline.std_price = std_price
            baseline.avg_trades_per_hour = avg_trades_per_hour
            baseline.last_updated = now
        else:
            baseline = Baseline(
                ticker=ticker,
                avg_volume=avg_volume,
                std_volume=std_volume,
                avg_price=avg_price,
                std_price=std_price,
                avg_trades_per_hour=avg_trades_per_hour,
                last_updated=now,
            )
            self.db.add(baseline)

        self.db.commit()

        return BaselineStats(
            ticker=ticker,
            avg_volume=avg_volume,
            std_volume=std_volume,
            avg_price=avg_price,
            std_price=std_price,
            avg_trades_per_hour=avg_trades_per_hour,
            last_updated=now,
        )

    # -------------------------------------------------------------------------
    # VOLUME ANOMALIES
    # -------------------------------------------------------------------------

    def detect_volume_anomaly(self, ticker: str, total_volume: float) -> Tuple[bool, float]:
        """Detect whether the latest volume is an anomaly based on baseline Z-score."""
        baseline = (
            self.db.query(Baseline)
            .filter_by(ticker=ticker)
            .first()
        )
        if not baseline or not baseline.std_volume:
            return False, 0.0

        zscore = (total_volume - baseline.avg_volume) / baseline.std_volume
        is_anomaly = zscore >= self.config["volume_zscore_threshold"]
        return is_anomaly, float(zscore)

    # -------------------------------------------------------------------------
    # VPIN CALCULATION
    # -------------------------------------------------------------------------

    def calculate_vpin(self, ticker: str, window_trades: Optional[int] = None) -> float:
        """Calculate VPIN (Volume-synchronized Probability of Informed Trading)."""
        window = window_trades or int(self.config["vpin_window_trades"])

        trades = (
            self.db.query(Trade)
            .filter(Trade.ticker == ticker)
            .order_by(Trade.timestamp.desc())
            .limit(window)
            .all()
        )
        if len(trades) < 10:
            return 0.0

        buy_volume = sum(t.volume for t in trades if t.side == "yes")
        sell_volume = sum(t.volume for t in trades if t.side == "no")

        total_volume = buy_volume + sell_volume
        if total_volume == 0:
            return 0.0

        # Standard VPIN: imbalance / total volume
        vpin = abs(buy_volume - sell_volume) / total_volume
        return float(vpin)

    # -------------------------------------------------------------------------
    # WHALE TRADES
    # -------------------------------------------------------------------------

    def detect_whale_trades(
        self,
        ticker: str,
        threshold_usd: Optional[float] = None,
        lookback_hours: int = 24,
    ) -> List[Dict]:
        """
        Detect abnormally large trades (whales).

        threshold_usd: if provided, overrides config['whale_threshold_usd'].
        """
        threshold = threshold_usd or self.config.get("whale_threshold_usd", 3000.0)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        trades = (
            self.db.query(Trade)
            .filter(Trade.ticker == ticker, Trade.timestamp >= cutoff)
            .all()
        )

        whales: List[Dict] = []
        for trade in trades:
            # Kalshi prices are in cents (0–100); 1 contract pays $1 at resolution.
            value_usd = float(trade.volume * trade.price / 100.0)
            if value_usd >= threshold:
                whales.append(
                    {
                        "trade_id": trade.trade_id,
                        "trader_id": getattr(trade, "trader_id", None),
                        "side": trade.side,
                        "volume": trade.volume,
                        "price": float(trade.price),
                        "value_usd": value_usd,
                        "timestamp": trade.timestamp.isoformat(),
                    }
                )

        return whales

    # -------------------------------------------------------------------------
    # PRICE/VOLUME CORRELATION
    # -------------------------------------------------------------------------

    def detect_price_volume_correlation(
        self,
        ticker: str,
        lookback_hours: int = 1,
    ) -> Tuple[bool, float]:
        """
        Detect coordinated price jump + volume surge (front-running signal).

        Returns issuspicious, correlationscore.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
        trades = (
            self.db.query(Trade)
            .filter(Trade.ticker == ticker, Trade.timestamp >= cutoff)
            .order_by(Trade.timestamp.asc())
            .all()
        )
        if len(trades) < 10:
            return False, 0.0

        prices = np.array([t.price for t in trades], dtype=float)
        volumes = np.array([t.volume for t in trades], dtype=float)

        if np.std(prices) == 0 or np.std(volumes) == 0:
            return False, 0.0

        corr = float(np.corrcoef(prices, volumes)[0, 1])
        issuspicious = abs(corr) >= 0.7
        return issuspicious, corr

    # -------------------------------------------------------------------------
    # ANOMALY SCORING & LOGGING
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
        Combine multiple signals into a single anomaly score.

        Rough weighting:
        - Volume Z-score
        - VPIN (order flow toxicity)
        - Time-to-resolution urgency
        - Price/volume correlation
        - Whale count
        """
        # Volume component
        volume_score = min(max(volume_zscore - 2.0, 0.0), 5.0)

        # VPIN component (0–1 scaled to 0–3)
        vpin_score = min(vpin * 3.0, 3.0)

        # Urgency: closer to resolution → higher urgency
        if days_to_close <= 0:
            urgency_score = 4.0
        elif days_to_close <= 1:
            urgency_score = 3.5
        elif days_to_close <= 3:
            urgency_score = 3.0
        elif days_to_close <= 7:
            urgency_score = 2.0
        elif days_to_close <= 14:
            urgency_score = 1.0
        else:
            urgency_score = 0.0

        # Price/volume correlation (0–3)
        corr_score = min(abs(price_volume_corr) * 3.0, 3.0)

        # Whale count (0–3)
        whale_score = min(whale_count * 1.5, 3.0)

        score = volume_score + vpin_score + urgency_score + corr_score + whale_score
        return float(score)

    def log_anomaly(
        self,
        ticker: str,
        anomaly_type: str,
        score: float,
        details: Dict,
    ) -> Anomaly:
        """Log anomaly with deduplication (avoid duplicate alerts)."""
        lookback = datetime.now(timezone.utc) - timedelta(hours=1)

        existing = (
            self.db.query(Anomaly)
            .filter(
                Anomaly.ticker == ticker,
                Anomaly.anomaly_type == anomaly_type,
                Anomaly.detected_at >= lookback,
                Anomaly.resolved.is_(False),
            )
            .first()
        )

        if existing:
            existing.score = max(existing.score, score)
            existing.details = details
            self.db.commit()
            return existing

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
            detected_at=datetime.now(timezone.utc),
            resolved=False,
        )

        self.db.add(anomaly)
        self.db.commit()
        self.db.refresh(anomaly)
        return anomaly

    # -------------------------------------------------------------------------
    # TRADER PROFILES (optional, for future use)
    # -------------------------------------------------------------------------

    def update_trader_profiles(self, lookback_days: int = 7) -> None:
        """Maintain trader profiles to identify persistent whales."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        trades = (
            self.db.query(Trade)
            .filter(Trade.timestamp >= cutoff)
            .all()
        )

        stats: Dict[str, Dict[str, float]] = {}
        for t in trades:
            if not t.trader_id:
                continue
            s = stats.setdefault(
                t.trader_id,
                {
                    "total_volume_usd": 0.0,
                    "total_trades": 0,
                },
            )
            value_usd = float(t.volume * t.price / 100.0)
            s["total_volume_usd"] += value_usd
            s["total_trades"] += 1

        for trader_id, s in stats.items():
            profile = (
                self.db.query(TraderProfile)
                .filter(TraderProfile.trader_id == trader_id)
                .first()
            )
            avg_trade_size = s["total_volume_usd"] / max(s["total_trades"], 1)

            is_whale = s["total_volume_usd"] >= self.config["soft_whale_threshold_usd"]

            if profile:
                profile.total_volume_usd = s["total_volume_usd"]
                profile.total_trades = s["total_trades"]
                profile.avg_trade_size_usd = avg_trade_size
                profile.is_whale = is_whale
            else:
                profile = TraderProfile(
                    trader_id=trader_id,
                    total_volume_usd=s["total_volume_usd"],
                    total_trades=s["total_trades"],
                    avg_trade_size_usd=avg_trade_size,
                    is_whale=is_whale,
                    first_seen=datetime.now(timezone.utc),
                )
                self.db.add(profile)

        self.db.commit()
