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
        """
        Initialize Kalshi API client with new authentication method.
        
        Args:
            api_key_id: Your API Key ID (looks like: a952bcbe-ec3b-4b5b-b8f9-11dae589608c)
            private_key_path: Path to your private key file (.key)
        """
        self.api_key_id = api_key_id
        self.private_key = self._load_private_key(private_key_path)
        
    def _load_private_key(self, key_path: str):
        """Load the RSA private key from file."""
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
        """Create RSA-PSS signature for the request."""
        # Remove query parameters before signing
        path_without_query = path.split('?')[0]
        
        # Create message: timestamp + method + path
        message = f"{timestamp}{method}{path_without_query}".encode('utf-8')
        
        # Sign with RSA-PSS
        signature = self.private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Return base64 encoded
        return base64.b64encode(signature).decode('utf-8')
    
    def _get_headers(self, method: str, path: str) -> Dict[str, str]:
        """Generate authentication headers for the request."""
        timestamp = str(int(time.time() * 1000))  # Milliseconds
        signature = self._create_signature(timestamp, method, path)
        
        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "Content-Type": "application/json"
        }
    
    async def get_markets(self, status: str = "open", limit: int = 100) -> List[Dict]:
        """Fetch active markets."""
        path = "/trade-api/v2/markets"
        headers = self._get_headers("GET", path)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/markets",
                headers=headers,
                params={"status": status, "limit": limit}
            )
            response.raise_for_status()
            return response.json().get("markets", [])
    
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
                params=params
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
                headers=headers
            )
            response.raise_for_status()
            return response.json()
