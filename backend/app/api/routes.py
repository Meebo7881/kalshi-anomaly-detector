from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, cast, Float, Integer, func
from app.core.database import get_db
from app.models.models import Market, Anomaly, Trade, TraderProfile
from app.services.detector import AnomalyDetector

router = APIRouter()

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
    }

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@router.get("/anomalies")
async def get_anomalies(
    db: Session = Depends(get_db),
    days: int = Query(7, ge=1, le=90),
    severity: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Get detected anomalies with optional filters."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = db.query(Anomaly).filter(Anomaly.detected_at >= cutoff)
    if severity:
        query = query.filter(Anomaly.severity == severity)
    total = query.count()
    anomalies = query.order_by(Anomaly.detected_at.desc()).offset(offset).limit(limit).all()
    has_more = (offset + len(anomalies)) < total
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
        "items": [format_anomaly(a) for a in anomalies],
    }

@router.get("/markets")
async def get_markets(
    db: Session = Depends(get_db),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """Get markets with optional filters."""
    query = db.query(Market)
    if status:
        query = query.filter(Market.status == status)
    if category:
        query = query.filter(Market.category == category)
    markets = query.limit(limit).all()
    return {
        "total": len(markets),
        "items": [
            {
                "ticker": m.ticker,
                "title": m.title,
                "category": m.category,
                "status": m.status,
                "close_date": m.close_date.isoformat() if m.close_date else None,
                "whale_trades_count": getattr(m, 'whale_trades_count', 0),
            }
            for m in markets
        ],
    }

@router.get("/markets/{ticker}")
async def get_market_detail(ticker: str, db: Session = Depends(get_db)):
    """Get detailed information for a specific market."""
    market = db.query(Market).filter(Market.ticker == ticker).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    recent_trades = (
        db.query(Trade)
        .filter(Trade.ticker == ticker)
        .order_by(Trade.timestamp.desc())
        .limit(20)
        .all()
    )
    
    anomalies = (
        db.query(Anomaly)
        .filter(Anomaly.ticker == ticker)
        .order_by(Anomaly.detected_at.desc())
        .limit(10)
        .all()
    )
    
    return {
        "ticker": market.ticker,
        "title": market.title,
        "category": market.category,
        "status": market.status,
        "close_date": market.close_date.isoformat() if market.close_date else None,
        "recent_trades": [
            {
                "price": float(t.price),
                "volume": t.volume,
                "side": t.side,
                "timestamp": t.timestamp.isoformat(),
            }
            for t in recent_trades
        ],
        "anomalies": [format_anomaly(a) for a in anomalies],
    }

@router.get("/stats/summary")
async def get_stats_summary(db: Session = Depends(get_db)):
    """Get summary statistics for the dashboard."""
    total_markets = db.query(Market).count()
    active_markets = db.query(Market).filter(Market.status == "active").count()
    total_anomalies = db.query(Anomaly).filter(Anomaly.resolved == False).count()
    critical_anomalies = (
        db.query(Anomaly)
        .filter(Anomaly.resolved == False, Anomaly.severity == "critical")
        .count()
    )
    
    return {
        "total_markets": total_markets,
        "active_markets": active_markets,
        "total_anomalies": total_anomalies,
        "critical_anomalies": critical_anomalies,
    }

@router.get("/stats/whales")
async def get_whale_stats(
    db: Session = Depends(get_db),
    hours: int = Query(24, ge=1, le=168),
    min_usd: float = Query(1000.0, ge=100.0),
    limit: int = Query(50, ge=1, le=200),
):
    """Get whale trades enriched with market metadata for copy-trading."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    
    results = (
        db.query(Trade, Market)
        .join(Market, Trade.ticker == Market.ticker)
        .filter(
            Trade.timestamp >= cutoff,
            (Trade.volume * Trade.price / 100.0) >= min_usd
        )
        .order_by((Trade.volume * Trade.price / 100.0).desc())
        .limit(limit)
        .all()
    )
    
    items = []
    for trade, market in results:
        usd_value = float(trade.volume * trade.price / 100.0)
        
        days_to_close = None
        if market.close_date:
            close_date_utc = market.close_date
            if close_date_utc.tzinfo is None:
                close_date_utc = close_date_utc.replace(tzinfo=timezone.utc)
            delta = close_date_utc - datetime.now(timezone.utc)
            days_to_close = delta.days
        
        kalshi_url = f"https://kalshi.com/markets/{trade.ticker}"
        
        items.append({
            "ticker": trade.ticker,
            "market_title": market.title,
            "side": trade.side,
            "volume": trade.volume,
            "price": float(trade.price),
            "usd_value": usd_value,
            "timestamp": trade.timestamp.isoformat(),
            "days_to_close": days_to_close,
            "kalshi_url": kalshi_url,
            "category": market.category,
        })
    
    return {
        "total": len(items),
        "items": items,
        "hours": hours,
        "min_usd": min_usd,
    }

@router.get("/stats/whale-patterns")
async def get_whale_patterns(
    db: Session = Depends(get_db),
    days: int = Query(7, ge=1, le=30),
    min_whales: int = Query(2, ge=1),
):
    """Identify markets with clustered whale activity (potential insider signals)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Find markets with multiple whale trades (simplified query)
    whale_clusters = (
        db.query(
            Trade.ticker,
            func.count(Trade.id).label('whale_count'),
            func.sum(Trade.volume * Trade.price / 100.0).label('total_whale_volume_usd'),
            func.max(Trade.timestamp).label('latest_whale_time'),
        )
        .filter(
            Trade.timestamp >= cutoff,
            (Trade.volume * Trade.price / 100.0) >= 500
        )
        .group_by(Trade.ticker)
        .having(func.count(Trade.id) >= min_whales)
        .order_by(func.count(Trade.id).desc())
        .limit(20)
        .all()
    )
    
    items = []
    for cluster in whale_clusters:
        # Get market details
        market = db.query(Market).filter(Market.ticker == cluster.ticker).first()
        
        if not market:
            continue
        
        # Calculate consensus: are whales aligned on one side?
        yes_whales = (
            db.query(func.count(Trade.id))
            .filter(
                Trade.ticker == cluster.ticker,
                Trade.timestamp >= cutoff,
                Trade.side == 'yes',
                (Trade.volume * Trade.price / 100.0) >= 500
            )
            .scalar() or 0
        )
        
        no_whales = (
            db.query(func.count(Trade.id))
            .filter(
                Trade.ticker == cluster.ticker,
                Trade.timestamp >= cutoff,
                Trade.side == 'no',
                (Trade.volume * Trade.price / 100.0) >= 500
            )
            .scalar() or 0
        )
        
        total_whales = yes_whales + no_whales
        consensus_side = 'yes' if yes_whales > no_whales else 'no' if no_whales > yes_whales else 'mixed'
        consensus_strength = max(yes_whales, no_whales) / total_whales if total_whales > 0 else 0
        
        # Days to close
        days_to_close = None
        if market.close_date:
            close_date_utc = market.close_date
            if close_date_utc.tzinfo is None:
                close_date_utc = close_date_utc.replace(tzinfo=timezone.utc)
            delta = close_date_utc - datetime.now(timezone.utc)
            days_to_close = delta.days
        
        items.append({
            'ticker': cluster.ticker,
            'market_title': market.title,
            'category': market.category,
            'whale_count': cluster.whale_count,
            'total_whale_volume_usd': float(cluster.total_whale_volume_usd or 0),
            'yes_whales': yes_whales,
            'no_whales': no_whales,
            'consensus_side': consensus_side,
            'consensus_strength': round(consensus_strength * 100, 1),
            'days_to_close': days_to_close,
            'latest_whale_time': cluster.latest_whale_time.isoformat() if cluster.latest_whale_time else None,
            'kalshi_url': f"https://kalshi.com/markets/{cluster.ticker}",
        })
    
    return {
        'total': len(items),
        'items': items,
        'days': days,
        'min_whales': min_whales,
    }
