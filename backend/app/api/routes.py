from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, cast, Float, Integer

from app.core.database import get_db
from app.models.models import Market, Anomaly, Trade, TraderProfile
from app.services.detector import AnomalyDetector

def format_anomaly(anomaly):
    """Format anomaly for API response."""
    return {
        "id": anomaly.id,
        "ticker": anomaly.ticker,
        "anomaly_type": anomaly.anomaly_type,
        "score": anomaly.score,
        "severity": anomaly.severity,
        "details": anomaly.details,
        "detected_at": anomaly.detected_at.isoformat(),
        "market": {
            "title": anomaly.market.title,
            "category": anomaly.market.category
        } if anomaly.market else None
    }

router = APIRouter()

@router.get("/stats/whales")
async def get_whale_stats(
    db: Session = Depends(get_db),
    hours: int = Query(24, ge=1, le=168),
    min_usd: float = Query(1000.0, ge=100.0),
    limit: int = Query(50, ge=1, le=200),
):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    trades = (
        db.query(Trade)
        .filter(Trade.timestamp >= cutoff)
        .filter((Trade.volume * Trade.price / 100.0) >= min_usd)
        .order_by((Trade.volume * Trade.price / 100.0).desc())
        .limit(limit)
        .all()
    )

    items = [
        {
            "ticker": t.ticker,
            "side": t.side,
            "volume": t.volume,
            "price": float(t.price),
            "usd_value": float(t.volume * t.price / 100.0),
            "timestamp": t.timestamp.isoformat(),
        }
        for t in trades
    ]

    return {
        "total": len(items),
        "items": items,
        "hours": hours,
        "min_usd": min_usd,
    }

@router.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@router.get("/markets")
async def get_markets(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all monitored markets with pagination."""
    query = db.query(Market)
    
    # Filter by category if provided
    if category:
        query = query.filter(Market.category == category)
    
    # Get total count
    total = query.count()
    
    # Get paginated results
    markets = query.order_by(Market.ticker).offset(skip).limit(limit).all()
    
    # Return paginated format matching frontend expectations
    return {
        "total": total,
        "items": [
            {
                "ticker": m.ticker,
                "title": m.title,
                "category": m.category,
                "status": m.status,
                "close_date": m.close_date.isoformat() if m.close_date else None,
            }
            for m in markets
        ],
        "skip": skip,
        "limit": limit
    }

@router.get("/anomalies")
async def get_anomalies(
    severity: Optional[str] = Query(None, regex="^(low|medium|high|critical)$"),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    min_vpin: Optional[float] = Query(None, ge=0.0, le=1.0),
    has_whales: Optional[bool] = Query(None),
    min_score: Optional[float] = Query(None, ge=0.0, le=10.0),
    ticker: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    # Build query with eager loading
    query = db.query(Anomaly).join(Market).options(joinedload(Anomaly.market))

    # Time filter
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = query.filter(Anomaly.detected_at >= cutoff)
    query = query.filter(Anomaly.resolved == False)

    # Apply all filters
    if severity:
        query = query.filter(Anomaly.severity == severity)
    if min_score is not None:
        query = query.filter(Anomaly.score >= min_score)
    if ticker:
        query = query.filter(Anomaly.ticker == ticker)
    if category:
        query = query.filter(Market.category == category)
    if min_vpin is not None:
        query = query.filter(cast(Anomaly.details['vpin'].astext, Float) >= min_vpin)
    if has_whales:
        query = query.filter(cast(Anomaly.details['whale_trades'].astext, Integer) > 0)

    total = query.count()
    anomalies = query.order_by(Anomaly.detected_at.desc()).limit(limit).offset(offset).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
        "items": [format_anomaly(a) for a in anomalies]
    }

@router.post("/anomalies/{anomaly_id}/resolve")
async def resolve_anomaly(anomaly_id: int, resolution_note: Optional[str] = None, db: Session = Depends(get_db)):
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    anomaly.resolved = True
    anomaly.resolved_at = datetime.now(timezone.utc)
    if resolution_note:
        if not anomaly.details:
            anomaly.details = {}
        anomaly.details['resolution_note'] = resolution_note
    db.commit()
    return {"message": "Anomaly marked as resolved", "anomaly_id": anomaly_id}

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
