#!/bin/bash

echo "================================"
echo "Kalshi API Connection Test"
echo "================================"

echo -e "\n1️⃣  Checking credentials..."
docker-compose exec -T api python -c "
from app.core.config import settings
print(f'✓ API Key ID set: {bool(settings.KALSHI_API_KEY_ID)}')
print(f'✓ Private Key Path: {settings.KALSHI_PRIVATE_KEY_PATH}')
" || echo "❌ Failed to check credentials"

echo -e "\n2️⃣  Testing network connectivity..."
docker-compose exec -T api curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" https://api.elections.kalshi.com/trade-api/v2/markets || echo "❌ Cannot reach Kalshi API"

echo -e "\n3️⃣  Testing authentication..."
docker-compose exec -T api python << 'PYTHON'
import asyncio
from app.services.kalshi_service import KalshiAPI
from app.core.config import settings

async def test():
    try:
        kalshi = KalshiAPI(settings.KALSHI_API_KEY_ID, settings.KALSHI_PRIVATE_KEY_PATH)
        markets = await kalshi.get_markets(limit=3)
        print(f"✅ Authentication successful! Fetched {len(markets)} markets")
        for m in markets[:2]:
            print(f"   • {m['ticker']}: {m['title'][:50]}...")
    except Exception as e:
        print(f"❌ Authentication failed: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test())
PYTHON

echo -e "\n4️⃣  Checking database for fetched data..."
docker-compose exec -T postgres psql -U kalshi_user -d kalshi_detector -c "
SELECT 
    (SELECT COUNT(*) FROM markets) as markets,
    (SELECT COUNT(*) FROM trades) as trades,
    (SELECT COUNT(*) FROM anomalies) as anomalies;
" || echo "❌ Database query failed"

echo -e "\n5️⃣  Checking worker status..."
docker-compose ps worker

echo -e "\n6️⃣  Recent worker logs..."
docker-compose logs --tail=10 worker

echo -e "\n================================"
echo "✅ Test Complete!"
echo "================================"
