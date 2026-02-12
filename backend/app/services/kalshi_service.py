import httpx
import base64
import time
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


class KalshiAPI:
    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

    def __init__(self, api_key_id: str, private_key_path: str, max_rps: float = 10.0):
        """
        max_rps: max requests per second you want to allow for this client.
                 For Kalshi Basic (20 rps read), 10 is a safe default.
        """
        self.api_key_id = api_key_id
        self.private_key = self._load_private_key(private_key_path)
        self.last_request_time = 0.0
        self.min_request_interval = 1.0 / max_rps if max_rps > 0 else 0.0

    # -------------------------------------------------------------------------
    # Auth helpers
    # -------------------------------------------------------------------------
    def _load_private_key(self, key_path: str):
        try:
            with open(key_path, "rb") as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None,
                )
            return private_key
        except Exception as e:
            print(f"Error loading private key: {e}")
            raise

    async def _rate_limit(self):
        """Ensure we don't exceed configured rate limits."""
        if self.min_request_interval <= 0:
            return
        now = time.time()
        time_since_last = now - self.last_request_time
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()

    def _create_signature(self, timestamp: str, method: str, path: str) -> str:
        path_without_query = path.split("?")[0]
        message = f"{timestamp}{method}{path_without_query}".encode("utf-8")
        signature = self.private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    def _get_headers(self, method: str, path: str) -> Dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        signature = self._create_signature(timestamp, method, path)
        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "Content-Type": "application/json",
        }

    # -------------------------------------------------------------------------
    # Account limits (optional helper)
    # -------------------------------------------------------------------------
    async def get_account_limits(self) -> Dict:
        """Optional: fetch your current API limits for logging/tuning."""
        await self._rate_limit()
        path = "/trade-api/v2/account/limits"
        headers = self._get_headers("GET", path)
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.BASE_URL}/account/limits",
                headers=headers,
                timeout=10.0,
            )
        resp.raise_for_status()
        return resp.json()

    # -------------------------------------------------------------------------
    # Events (with pagination)
    # -------------------------------------------------------------------------
    async def get_events(self, status: str = "open", limit: int = 200) -> List[Dict]:
        """Fetch a single page of events."""
        await self._rate_limit()
        path = "/trade-api/v2/events"
        headers = self._get_headers("GET", path)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/events",
                headers=headers,
                params={"status": status, "limit": limit},
                timeout=30.0,
            )
        response.raise_for_status()
        return response.json().get("events", [])

    async def get_all_events(
        self, status: str = "open", page_limit: int = 200
    ) -> List[Dict]:
        """Fetch all events via cursor-based pagination."""
        path = "/trade-api/v2/events"
        headers = self._get_headers("GET", path)
        all_events: List[Dict] = []
        cursor: Optional[str] = None

        async with httpx.AsyncClient() as client:
            while True:
                await self._rate_limit()
                params = {"status": status, "limit": page_limit}
                if cursor:
                    params["cursor"] = cursor

                resp = await client.get(
                    f"{self.BASE_URL}/events",
                    headers=headers,
                    params=params,
                    timeout=30.0,
                )
                resp.raise_for_status()
                data = resp.json()
                batch = data.get("events", [])
                all_events.extend(batch)

                cursor = data.get("cursor")
                if not cursor or not batch:
                    break

        print(f"Fetched {len(all_events)} events total")
        return all_events

    # -------------------------------------------------------------------------
    # Markets (single page and full pagination)
    # -------------------------------------------------------------------------
    async def get_markets_for_event(
        self, event_ticker: str, status: str = "open"
    ) -> List[Dict]:
        """Get all markets for a specific event (single call)."""
        await self._rate_limit()
        path = "/trade-api/v2/markets"
        headers = self._get_headers("GET", path)
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/markets",
                    headers=headers,
                    params={"event_ticker": event_ticker, "status": status, "limit": 1000},
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.json().get("markets", [])
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    # Rate limited - wait and skip this event
                    print(f"429 rate limit for event {event_ticker}, skipping after delay")
                    await asyncio.sleep(2)
                    return []
                raise

    async def get_markets(
        self, status: str = "open", limit: int = 1000
    ) -> List[Dict]:
        """Fetch a single page of markets."""
        await self._rate_limit()
        path = "/trade-api/v2/markets"
        headers = self._get_headers("GET", path)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/markets",
                headers=headers,
                params={"status": status, "limit": min(limit, 1000)},
                timeout=30.0,
            )
        response.raise_for_status()
        return response.json().get("markets", [])

    async def get_all_markets(
        self, status: str = "open", page_limit: int = 1000
    ) -> List[Dict]:
        """Fetch all markets via cursor-based pagination."""
        path = "/trade-api/v2/markets"
        headers = self._get_headers("GET", path)
        all_markets: List[Dict] = []
        cursor: Optional[str] = None

        async with httpx.AsyncClient() as client:
            while True:
                await self._rate_limit()
                params = {"status": status, "limit": page_limit}
                if cursor:
                    params["cursor"] = cursor

                resp = await client.get(
                    f"{self.BASE_URL}/markets",
                    headers=headers,
                    params=params,
                    timeout=30.0,
                )
                resp.raise_for_status()
                data = resp.json()
                batch = data.get("markets", [])
                all_markets.extend(batch)

                cursor = data.get("cursor")
                if not cursor or not batch:
                    break

        print(f"Fetched {len(all_markets)} markets total")
        return all_markets

    async def get_all_markets_from_events(
        self, categories: List[str] = None
    ) -> List[Dict]:
        """
        Get markets for events in specific categories, annotating markets with:
          - category (event category)
          - event_title (event question)
        """
        all_markets: List[Dict] = []

        # Fetch all open events
        events = await self.get_all_events(status="open", page_limit=200)

        # Filter by category if specified
        if categories:
            events = [e for e in events if e.get("category") in categories]
        print(f"Found {len(events)} events in specified categories")

        # For each event, fetch markets
        for event in events[:50]:  # adjust this cap as needed
            try:
                event_ticker = event["event_ticker"]
                event_category = event.get("category")
                event_title = event.get("title")

                markets = await self.get_markets_for_event(event_ticker)
                if markets:
                    for m in markets:
                        m["category"] = event_category
                        m["event_title"] = event_title
                        all_markets.append(m)
                    print(f" • {event_ticker}: {len(markets)} markets")

            except Exception as e:
                print(f" ⚠️ Error fetching markets for {event_ticker}: {e}")
                continue

        print(f"Total markets from events: {len(all_markets)}")
        return all_markets

    # -------------------------------------------------------------------------
    # Trades & orderbook
    # -------------------------------------------------------------------------
    async def get_trades(
        self, ticker: str, min_ts: Optional[int] = None
    ) -> List[Dict]:
        """Fetch trade history for a market."""
        await self._rate_limit()
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
                timeout=30.0,
            )
        response.raise_for_status()
        return response.json().get("trades", [])

    async def get_orderbook(self, ticker: str) -> Dict:
        """Get current orderbook."""
        await self._rate_limit()
        path = f"/trade-api/v2/markets/{ticker}/orderbook"
        headers = self._get_headers("GET", path)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}/markets/{ticker}/orderbook",
                headers=headers,
                timeout=30.0,
            )
        response.raise_for_status()
        return response.json()
