from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.database import engine, get_db
from app.models import models
from app.models.models import Anomaly, Market

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "healthy", "service": "Kalshi Anomaly Detector"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        # Fixed: Use text() for raw SQL in SQLAlchemy 2.0
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {str(e)}")

@app.get(f"{settings.API_V1_STR}/anomalies")
def get_anomalies(severity: str = None, days: int = 7, db: Session = Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(days=days)
    query = db.query(Anomaly).filter(Anomaly.detected_at >= cutoff)
    
    if severity:
        query = query.filter(Anomaly.severity == severity)
    
    anomalies = query.order_by(Anomaly.detected_at.desc()).limit(100).all()
    
    return [{
        "id": a.id,
        "ticker": a.ticker,
        "type": a.anomaly_type,
        "score": a.score,
        "severity": a.severity,
        "details": a.details,
        "detected_at": a.detected_at.isoformat()
    } for a in anomalies]

@app.get(f"{settings.API_V1_STR}/markets")
def get_markets(db: Session = Depends(get_db)):
    markets = db.query(Market).filter_by(status="active").all()
    return [{
        "ticker": m.ticker,
        "title": m.title,
        "category": m.category,
        "close_date": m.close_date.isoformat() if m.close_date else None
    } for m in markets]

@app.get(f"{settings.API_V1_STR}/markets/{{ticker}}/anomalies")
def get_market_anomalies(ticker: str, db: Session = Depends(get_db)):
    anomalies = db.query(Anomaly).filter_by(ticker=ticker)\
        .order_by(Anomaly.detected_at.desc()).limit(50).all()
    
    return [{
        "id": a.id,
        "score": a.score,
        "severity": a.severity,
        "type": a.anomaly_type,
        "details": a.details,
        "detected_at": a.detected_at.isoformat()
    } for a in anomalies]
