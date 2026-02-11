# Updated trade collection with proper timestamp parsing
import asyncio
from app.services.kalshi_service import KalshiAPI
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.models import Trade, Market
from datetime import datetime

async def collect_political_trades_fixed():
    kalshi = KalshiAPI(settings.KALSHI_API_KEY_ID, settings.KALSHI_PRIVATE_KEY_PATH)
    db = SessionLocal()
    
    print("Collecting trades for political markets (FIXED)...\n")
    
    # Get Trump pardon markets
    markets = await kalshi.get_markets_for_event('KXTRUMPPARDONS-29JAN21')
    
    total_trades = 0
    
    for market in markets[:10]:  # Test with first 10
        ticker = market['ticker']
        title = market['title'][:50]
        
        # Ensure market exists in DB
        db_market = db.query(Market).filter_by(ticker=ticker).first()
        if not db_market:
            db_market = Market(
                ticker=ticker,
                title=market['title'],
                category='Politics',
                close_date=datetime.fromisoformat(market['close_time'].replace('Z', '+00:00'))
            )
            db.add(db_market)
            db.commit()
        
        # Get trades
        try:
            trades = await kalshi.get_trades(ticker)
            
            if trades:
                print(f"📊 {ticker[:40]}: {len(trades)} trades")
                
                for trade in trades:
                    try:
                        # Handle different timestamp formats
                        created_time = trade.get("created_time")
                        
                        if isinstance(created_time, str):
                            # ISO format string
                            timestamp = datetime.fromisoformat(created_time.replace('Z', '+00:00'))
                        elif isinstance(created_time, (int, float)):
                            # Unix timestamp
                            if created_time > 9999999999:
                                timestamp = datetime.fromtimestamp(created_time / 1000)
                            else:
                                timestamp = datetime.fromtimestamp(created_time)
                        else:
                            # Fallback to now
                            timestamp = datetime.utcnow()
                        
                        # Get price (handle different field names)
                        price = float(trade.get("yes_price", trade.get("price", 0)))
                        
                        # Get volume
                        volume = int(trade.get("count", trade.get("volume", trade.get("size", 1))))
                        
                        # Get side
                        side = trade.get("taker_side", trade.get("side", "unknown"))
                        
                        # Create trade ID
                        trade_id = str(trade.get("trade_id", f"{ticker}_{created_time}"))
                        
                        db_trade = Trade(
                            ticker=ticker,
                            trade_id=trade_id,
                            price=price,
                            volume=volume,
                            side=side,
                            timestamp=timestamp
                        )
                        db.merge(db_trade)
                        total_trades += 1
                        
                    except Exception as e:
                        print(f"  Error with trade: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                
                db.commit()
                print(f"  ✅ Stored {total_trades} total trades so far")
        except Exception as e:
            print(f"  Error fetching trades: {e}")
    
    print(f"\n✅ Successfully stored {total_trades} trades from Trump pardon markets")
    db.close()

asyncio.run(collect_political_trades_fixed())
