from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.models import Market, Anomaly, Trade, TraderProfile
from app.services.detector import AnomalyDetector

router = APIRouter()

@router.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@router.get("/markets")
async def get_markets(db: Session = Depends(get_db)):
    """Get all monitored markets."""
    markets = db.query(Market).all()
    return [
        {
            "ticker": m.ticker,
            "title": m.title,
            "category": m.category,
            "status": m.status,
            "close_date": m.close_date.isoformat() if m.close_date else None
        }
        for m in markets
    ]

@router.get("/anomalies")
async def get_anomalies(
    severity: str = None,
    days: int = 7,
    db: Session = Depends(get_db)
):
    """Get detected anomalies."""
    query = db.query(Anomaly)
    
    # Filter by time
    cutoff = datetime.utcnow() - timedelta(days=days)
    query = query.filter(Anomaly.detected_at >= cutoff)
    
    # Filter by severity
    if severity:
        query = query.filter(Anomaly.severity == severity)
    
    anomalies = query.order_by(Anomaly.detected_at.desc()).all()
    
    return [
        {
            "id": a.id,
            "ticker": a.ticker,
            "anomaly_type": a.anomaly_type,
            "score": float(a.score),
            "severity": a.severity,
            "details": a.details,
            "detected_at": a.detected_at.isoformat()
        }
        for a in anomalies
    ]

@router.get("/markets/{ticker}")
async def get_market(ticker: str, db: Session = Depends(get_db)):
    """Get details for a specific market."""
    market = db.query(Market).filter(Market.ticker == ticker).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    # Get recent trades
    trades = db.query(Trade).filter(
        Trade.ticker == ticker
    ).order_by(Trade.timestamp.desc()).limit(100).all()
    
    # Get anomalies
    anomalies = db.query(Anomaly).filter(
        Anomaly.ticker == ticker
    ).order_by(Anomaly.detected_at.desc()).limit(10).all()
    
    return {
        "ticker": market.ticker,
        "title": market.title,
        "category": market.category,
        "status": market.status,
        "close_date": market.close_date.isoformat() if market.close_date else None,
        "trades_count": len(trades),
        "recent_trades": [
            {
                "price": float(t.price),
                "volume": t.volume,
                "side": t.side,
                "timestamp": t.timestamp.isoformat()
            }
            for t in trades[:10]
        ],
        "anomalies": [
            {
                "type": a.anomaly_type,
                "score": float(a.score),
                "severity": a.severity,
                "detected_at": a.detected_at.isoformat()
            }
            for a in anomalies
        ]
    }

@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get system statistics."""
    total_markets = db.query(Market).count()
    total_trades = db.query(Trade).count()
    total_anomalies = db.query(Anomaly).count()
    
    high_severity = db.query(Anomaly).filter(Anomaly.severity == "high").count()
    medium_severity = db.query(Anomaly).filter(Anomaly.severity == "medium").count()
    low_severity = db.query(Anomaly).filter(Anomaly.severity == "low").count()
    
    return {
        "total_markets": total_markets,
        "total_trades": total_trades,
        "total_anomalies": total_anomalies,
        "anomalies_by_severity": {
            "high": high_severity,
            "medium": medium_severity,
            "low": low_severity
        }
    }

@router.get("/anomalies/{ticker}/details")
async def get_anomaly_details(ticker: str, db: Session = Depends(get_db)):
    """Get detailed anomaly info including VPIN, whales, correlations."""
    detector = AnomalyDetector(db)
    
    # Get recent anomalies
    anomalies = (
        db.query(Anomaly)
        .filter(Anomaly.ticker == ticker)
        .order_by(Anomaly.detected_at.desc())
        .limit(10)
        .all()
    )
    
    # Get current VPIN
    vpin = detector.calculate_vpin(ticker)
    
    # Get whale trades
    whales = detector.detect_whale_trades(ticker, threshold_usd=2000)
    
    # Get price-volume correlation
    is_correlated, corr_score = detector.detect_price_volume_correlation(ticker)
    
    return {
        "ticker": ticker,
        "vpin": vpin,
        "whale_trades": whales,
        "price_volume_correlation": {
            "is_suspicious": is_correlated,
            "score": corr_score
        },
        "recent_anomalies": [
            {
                "id": a.id,
                "score": a.score,
                "severity": a.severity,
                "detected_at": a.detected_at.isoformat(),
                "details": a.details
            }
            for a in anomalies
        ]
    }


@router.get("/stats/whales")
async def get_whale_stats(db: Session = Depends(get_db)):
    """Get top whale traders across all markets."""
    profiles = (
        db.query(TraderProfile)
        .filter(TraderProfile.is_whale == True)
        .order_by(TraderProfile.total_volume_usd.desc())
        .limit(20)
        .all()
    )
    
    return {
        "whale_count": len(profiles),
        "top_whales": [
            {
                "trader_id": p.trader_id,
                "total_trades": p.total_trades,
                "total_volume_usd": p.total_volume_usd,
                "avg_trade_size_usd": p.avg_trade_size_usd,
                "first_seen": p.first_seen.isoformat() if p.first_seen else None
            }
            for p in profiles
        ]
    }
