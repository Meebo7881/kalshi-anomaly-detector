from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey,Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Market(Base):
    __tablename__ = "markets"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    category = Column(String, index=True)
    close_date = Column(DateTime)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    trades = relationship("Trade", back_populates="market")
    anomalies = relationship("Anomaly", back_populates="market")
    baselines = relationship("Baseline", back_populates="market")

class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, ForeignKey("markets.ticker"), index=True, nullable=False)
    trade_id = Column(String, unique=True, index=True, nullable=False)
    price = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    side = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # trader tracking
    trader_id = Column(String, nullable=True, index=True)  # Kalshi user ID if available
    trade_value_usd = Column(Float, nullable=True)  # volume * price
    
    market = relationship("Market", back_populates="trades")

class Anomaly(Base):
    __tablename__ = "anomalies"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, ForeignKey("markets.ticker"), index=True, nullable=False)
    anomaly_type = Column(String, nullable=False)
    score = Column(Float, nullable=False)
    severity = Column(String)  # low, medium, high
    details = Column(JSON)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    market = relationship("Market", back_populates="anomalies")

class Baseline(Base):
    __tablename__ = "baselines"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, ForeignKey("markets.ticker"), index=True, nullable=False)
    avg_volume = Column(Float, nullable=False)
    std_volume = Column(Float, nullable=False)
    avg_price_change = Column(Float)
    calculated_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    market = relationship("Market", back_populates="baselines")

class TraderProfile(Base):
    __tablename__ = "trader_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    trader_id = Column(String, unique=True, index=True)
    first_seen = Column(DateTime)
    total_trades = Column(Integer, default=0)
    total_volume_usd = Column(Float, default=0.0)
    avg_trade_size_usd = Column(Float, default=0.0)
    is_whale = Column(Boolean, default=False)
    last_updated = Column(DateTime)
