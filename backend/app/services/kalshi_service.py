import httpx
import base64
import time
from typing import List, Dict, Optional
from datetime import datetime
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

class KalshiAPI:
    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
    
    def __init__(self, api_key_id: str, private_key_path: str):
        self.api_key_id = api_key_id
        self.private_key = self._load_private_key(private_key_path)
        
    def _load_private_key(self, key_path: str):
        try:
            with open(key_path, 'rb') as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None
                )
            return private_key
        except Exception as e:
            print(f"Error loading private key: {e}")
            raise
    
    def _create_signature(self, timestamp: str, method: str, path: str) -> str:
        path_without_query = path.split('?')[0]
        message = f"{timestamp}{method}{path_without_query}".encode('utf-8')
        
        signature = self.private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )
        
        return base64.b64encode(signature).decode('utf-8')
    
    def _get_headers(self, method: str, path: str) -> Dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        signature = self._create_signature(timestamp, method, path)
        
        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "Content-Type": "application/json"
        }
    
    async def get_events(self, status: str = "open", limit: int = 200) -> List[Dict]:
        """Fetch events (long-term questions)."""
        path = "/trade-api/v2/events"
        headers = self._get_headers("GET", path)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/events",
                headers=headers,
                params={"status": status, "limit": limit},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("events", [])
    
    async def get_markets_for_event(self, event_ticker: str, status: str = "open") -> List[Dict]:
        """Get all markets for a specific event."""
        path = "/trade-api/v2/markets"
        headers = self._get_headers("GET", path)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/markets",
                headers=headers,
                params={"event_ticker": event_ticker, "status": status, "limit": 1000},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("markets", [])
    
    async def get_markets(self, status: str = "open", limit: int = 1000) -> List[Dict]:
        """Fetch active markets."""
        path = "/trade-api/v2/markets"
        headers = self._get_headers("GET", path)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/markets",
                headers=headers,
                params={"status": status, "limit": min(limit, 1000)},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("markets", [])
    
    async def get_all_markets_from_events(self, categories: List[str] = None) -> List[Dict]:
        """Get markets from specific event categories."""
        all_markets = []
        
        # Get events
        events = await self.get_events(status="open", limit=200)
        
        # Filter by category if specified
        if categories:
            events = [e for e in events if e.get('category') in categories]
        
        print(f"Found {len(events)} events in specified categories")
        
        # Get markets for each event
        for event in events[:50]:  # Limit to 50 events to avoid rate limits
            try:
                event_ticker = event['event_ticker']
                markets = await self.get_markets_for_event(event_ticker)
                if markets:
                    all_markets.extend(markets)
                    print(f"  • {event_ticker}: {len(markets)} markets")
            except Exception as e:
                print(f"  ⚠️  Error fetching markets for {event_ticker}: {e}")
                continue
        
        return all_markets
    
    async def get_trades(self, ticker: str, min_ts: Optional[int] = None) -> List[Dict]:
        """Fetch trade history for a market."""
        path = "/trade-api/v2/markets/trades"
        headers = self._get_headers("GET", path)
        
        params = {"ticker": ticker, "limit": 1000}
        if min_ts:
            params["min_ts"] = min_ts
            
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/markets/trades",
                headers=headers,
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json().get("trades", [])
    
    async def get_orderbook(self, ticker: str) -> Dict:
        """Get current orderbook."""
        path = f"/trade-api/v2/markets/{ticker}/orderbook"
        headers = self._get_headers("GET", path)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/markets/{ticker}/orderbook",
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
