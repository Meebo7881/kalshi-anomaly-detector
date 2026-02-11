from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Market(Base):
    __tablename__ = "markets"
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String, unique=True, nullable=False, index=True)
    title = Column(String, nullable=False)
    category = Column(String)
    close_date = Column(DateTime)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_ticker_status', 'ticker', 'status'),
    )

class Trade(Base):
    __tablename__ = "trades"
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String, nullable=False, index=True)
    trade_id = Column(String, unique=True)
    price = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    side = Column(String, nullable=True)  # Made nullable
    timestamp = Column(DateTime, nullable=False, index=True)
    
    __table_args__ = (
        Index('idx_ticker_timestamp', 'ticker', 'timestamp'),
    )

class MarketBaseline(Base):
    __tablename__ = "market_baselines"
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String, nullable=False, unique=True)
    avg_volume = Column(Float, nullable=False)
    std_volume = Column(Float, nullable=False)
    avg_price = Column(Float, nullable=False)
    std_price = Column(Float, nullable=False)
    avg_trades_per_hour = Column(Float)
    last_updated = Column(DateTime, default=datetime.utcnow)

class Anomaly(Base):
    __tablename__ = "anomalies"
    
    id = Column(Integer, primary_key=True)
    ticker = Column(String, nullable=False, index=True)
    anomaly_type = Column(String)
    score = Column(Float, nullable=False)
    severity = Column(String)
    details = Column(JSON)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('idx_severity_detected', 'severity', 'detected_at'),
    )
