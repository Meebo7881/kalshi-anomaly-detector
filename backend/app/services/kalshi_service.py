import httpx
from typing import List, Dict, Optional
from datetime import datetime, timedelta

class KalshiAPI:
    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.token = None
        self.token_expiry = None
        
    async def _get_headers(self) -> Dict[str, str]:
        if not self.token or datetime.now() > self.token_expiry:
            await self._refresh_token()
        
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    async def _refresh_token(self):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/login",
                json={"email": self.api_key, "password": self.api_secret}
            )
            data = response.json()
            self.token = data["token"]
            self.token_expiry = datetime.now() + timedelta(hours=12)
    
    async def get_markets(self, status: str = "open", limit: int = 100) -> List[Dict]:
        headers = await self._get_headers()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/markets",
                headers=headers,
                params={"status": status, "limit": limit}
            )
            return response.json().get("markets", [])
    
    async def get_trades(self, ticker: str, min_ts: Optional[int] = None) -> List[Dict]:
        headers = await self._get_headers()
        params = {"ticker": ticker, "limit": 1000}
        if min_ts:
            params["min_ts"] = min_ts
            
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/markets/trades",
                headers=headers,
                params=params
            )
            return response.json().get("trades", [])
    
    async def get_orderbook(self, ticker: str) -> Dict:
        headers = await self._get_headers()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/markets/{ticker}/orderbook",
                headers=headers
            )
            return response.json()
