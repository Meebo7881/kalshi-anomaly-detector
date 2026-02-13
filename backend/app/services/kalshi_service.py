"""
Kalshi API Service - Complete Rewrite
=====================================

IMPROVEMENTS FROM ORIGINAL:
1. Distributed rate limiting using Redis (prevents multi-worker violations)
2. Automatic retry with exponential backoff using tenacity
3. Comprehensive error handling and logging
4. Configurable rate limits and timeouts
5. Proper async/await patterns
6. Request/response logging for debugging
7. Health check methods
8. Batch request support with concurrency control

USAGE:
    from app.services.kalshi_service import KalshiAPI

    kalshi = KalshiAPI(
        api_key_id="your_key_id",
        private_key_path="/path/to/key.pem",
        max_rps=10.0,
        redis_url="redis://localhost:6379/0"
    )

    # Fetch markets
    markets = await kalshi.get_markets(status="open", limit=200)

    # Fetch trades
    trades = await kalshi.get_trades("PRES-2024")
"""

import httpx
import base64
import time
import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("Redis not available, using local rate limiting only")

logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """Rate limiting strategy."""
    DISTRIBUTED = "distributed"  # Redis-based, shared across workers
    LOCAL = "local"              # Per-instance only


@dataclass
class APIMetrics:
    """Track API usage metrics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limited_requests: int = 0
    total_request_time: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def avg_request_time(self) -> float:
        if self.successful_requests == 0:
            return 0.0
        return self.total_request_time / self.successful_requests


class KalshiAPI:
    """
    Enhanced Kalshi API client with distributed rate limiting and retry logic.

    Features:
    - Distributed rate limiting across multiple workers using Redis
    - Automatic retry with exponential backoff
    - Comprehensive error handling
    - Request/response logging
    - API usage metrics tracking
    - Support for all major Kalshi endpoints
    """

    BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"

    def __init__(
        self,
        api_key_id: str,
        private_key_path: str,
        max_rps: float = 10.0,
        redis_url: Optional[str] = None,
        default_timeout: float = 30.0,
        enable_metrics: bool = True
    ):
        """
        Initialize Kalshi API client.

        Args:
            api_key_id: Your Kalshi API key ID
            private_key_path: Path to your RSA private key file
            max_rps: Maximum requests per second (default: 10 for Basic tier)
            redis_url: Redis connection URL for distributed rate limiting
            default_timeout: Default timeout for API requests in seconds
            enable_metrics: Whether to track API usage metrics
        """
        self.api_key_id = api_key_id
        self.private_key = self._load_private_key(private_key_path)
        self.max_rps = max_rps or 8.0
        self.default_timeout = default_timeout
        self.min_request_interval = 1.0 / max_rps if max_rps > 0 else 0.0

        # Rate limiting strategy
        self.redis: Optional[redis.Redis] = None
        self.rate_limit_strategy = RateLimitStrategy.LOCAL

        if redis_url and REDIS_AVAILABLE:
            try:
                self.redis = redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=5,
                    socket_timeout=5
                )
                # Test connection
                self.redis.ping()
                self.rate_limit_strategy = RateLimitStrategy.DISTRIBUTED
                logger.info(
                    f"✅ Connected to Redis for distributed rate limiting "
                    f"(max {max_rps} rps)"
                )
            except Exception as e:
                logger.warning(
                    f"⚠️  Redis connection failed: {e}. "
                    f"Falling back to local rate limiting"
                )
                self.redis = None

        # Local rate limiting fallback
        self._last_request_time: float = 0.0
        self._request_count: int = 0

        # Metrics tracking
        self.enable_metrics = enable_metrics
        self.metrics = APIMetrics() if enable_metrics else None

        logger.info(
            f"Initialized KalshiAPI client "
            f"(strategy: {self.rate_limit_strategy.value}, "
            f"max_rps: {max_rps})"
        )

    # ========================================================================
    # AUTHENTICATION & SIGNATURE
    # ========================================================================

    def _load_private_key(self, key_path: str):
        """
        Load RSA private key from PEM file.

        Args:
            key_path: Path to PEM-encoded private key file

        Returns:
            Loaded private key object

        Raises:
            FileNotFoundError: If key file doesn't exist
            ValueError: If key file is invalid
        """
        try:
            with open(key_path, "rb") as key_file:
                private_key = serialization.load_pem_private_key(
                    key_file.read(),
                    password=None
                )
            logger.info(f"✅ Loaded private key from {key_path}")
            return private_key
        except FileNotFoundError:
            logger.error(f"❌ Private key file not found: {key_path}")
            raise
        except Exception as e:
            logger.error(f"❌ Error loading private key: {e}")
            raise ValueError(f"Invalid private key file: {e}")

    def _create_signature(self, timestamp: str, method: str, path: str) -> str:
        """
        Create request signature using RSA private key.

        Args:
            timestamp: Request timestamp in milliseconds
            method: HTTP method (GET, POST, etc.)
            path: API path without query parameters

        Returns:
            Base64-encoded signature
        """
        # Remove query parameters from path
        path_without_query = path.split("?")[0]

        # Create message: timestamp + method + path
        message = f"{timestamp}{method}{path_without_query}".encode("utf-8")

        # Sign with RSA-PSS
        signature = self.private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )

        return base64.b64encode(signature).decode("utf-8")

    def _get_headers(self, method: str, path: str) -> Dict[str, str]:
        """
        Generate request headers with authentication signature.

        Args:
            method: HTTP method
            path: API path

        Returns:
            Dictionary of headers including signature
        """
        timestamp = str(int(time.time() * 1000))
        signature = self._create_signature(timestamp, method, path)

        return {
            "KALSHI-ACCESS-KEY": self.api_key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "Content-Type": "application/json",
            "User-Agent": "KalshiAnomalyDetector/2.0"
        }

    # ========================================================================
    # RATE LIMITING
    # ========================================================================

    async def _rate_limit_distributed(self) -> None:
        """
        Distributed rate limiting using Redis sorted sets.

        Uses sliding window algorithm to track requests across all workers.
        Ensures global rate limit compliance even with multiple containers.
        """
        if not self.redis:
            await self._rate_limit_local()
            return

        key = "kalshi:api:ratelimit:global"
        now = time.time()
        window = 1.0  # 1 second sliding window

        try:
            pipe = self.redis.pipeline()

            # Remove requests older than the window
            pipe.zremrangebyscore(key, 0, now - window)

            # Count current requests in window
            pipe.zcard(key)

            # Add this request with timestamp as score and unique ID
            request_id = f"{now}:{id(self)}:{self._request_count}"
            pipe.zadd(key, {request_id: now})

            # Set key expiration (cleanup)
            pipe.expire(key, 5)

            # Execute pipeline
            results = pipe.execute()
            count_before = results[1]  # Result from zcard

            # If we're at or over the limit, sleep
            if count_before >= self.max_rps:
                sleep_time = window / self.max_rps
                logger.debug(
                    f"Rate limit reached ({count_before}/{self.max_rps} rps), "
                    f"sleeping {sleep_time:.3f}s"
                )
                if self.metrics:
                    self.metrics.rate_limited_requests += 1
                await asyncio.sleep(sleep_time)

            self._request_count += 1

        except redis.RedisError as e:
            logger.warning(f"Redis rate limit error: {e}, using local fallback")
            await self._rate_limit_local()

    async def _rate_limit_local(self) -> None:
        """
        Local (per-instance) rate limiting fallback.

        Uses simple token bucket algorithm with minimum interval between requests.
        Only enforces rate limit for this specific instance.
        """
        if self.min_request_interval <= 0:
            return

        now = time.time()
        time_since_last = now - self._last_request_time

        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            logger.debug(f"Local rate limit, sleeping {sleep_time:.3f}s")
            await asyncio.sleep(sleep_time)

        self._last_request_time = time.time()
        self._request_count += 1

    async def _enforce_rate_limit(self) -> None:
        """Apply rate limiting based on configured strategy."""
        if self.rate_limit_strategy == RateLimitStrategy.DISTRIBUTED:
            await self._rate_limit_distributed()
        else:
            await self._rate_limit_local()

    # ========================================================================
    # HTTP REQUEST WRAPPER
    # ========================================================================

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            httpx.HTTPStatusError,
            httpx.TimeoutException,
            httpx.ConnectError
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        timeout: Optional[float] = None
    ) -> Dict:
        """
        Make HTTP request to Kalshi API with retry logic.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            path: API endpoint path
            params: Query parameters
            json_data: JSON body for POST/PUT requests
            timeout: Request timeout (uses default if None)

        Returns:
            Parsed JSON response

        Raises:
            httpx.HTTPStatusError: For 4xx/5xx responses
            httpx.TimeoutException: For timeout errors
        """
        # Enforce rate limiting
        await self._enforce_rate_limit()

        # Prepare request
        url = f"{self.BASE_URL}{path}"
        headers = self._get_headers(method, path)
        timeout_val = timeout or self.default_timeout

        start_time = time.time()

        if self.metrics:
            self.metrics.total_requests += 1

        try:
            async with httpx.AsyncClient(timeout=timeout_val) as client:
                logger.debug(f"{method} {path} {params or ''}")

                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    json=json_data
                )

                request_time = time.time() - start_time

                # Log response
                logger.debug(
                    f"Response: {response.status_code} "
                    f"({request_time:.2f}s)"
                )

                # Raise for 4xx/5xx status codes
                response.raise_for_status()

                # Update metrics
                if self.metrics:
                    self.metrics.successful_requests += 1
                    self.metrics.total_request_time += request_time

                return response.json()

        except httpx.HTTPStatusError as e:
            if self.metrics:
                self.metrics.failed_requests += 1

            # Special handling for common status codes
            if e.response.status_code == 429:
                logger.error(
                    f"Rate limit exceeded (429) on {path}. "
                    f"This should not happen with rate limiting enabled!"
                )
                # Let tenacity retry with exponential backoff
                raise
            elif e.response.status_code == 404:
                logger.warning(f"Resource not found (404): {path}")
                return {}  # Return empty dict for 404
            elif e.response.status_code >= 500:
                logger.error(f"Server error ({e.response.status_code}): {path}")
                raise
            else:
                logger.error(f"HTTP error ({e.response.status_code}): {e}")
                raise

        except httpx.TimeoutException:
            if self.metrics:
                self.metrics.failed_requests += 1
            logger.error(f"Timeout on {method} {path} (>{timeout_val}s)")
            raise

        except Exception as e:
            if self.metrics:
                self.metrics.failed_requests += 1
            logger.error(f"Unexpected error on {method} {path}: {e}")
            raise

    # ========================================================================
    # EVENTS
    # ========================================================================

    async def get_events(
        self,
        status: str = "open",
        limit: int = 200,
        cursor: Optional[str] = None
    ) -> Tuple[List[Dict], Optional[str]]:
        """
        Get a page of events.

        Args:
            status: Event status (open, closed, settled)
            limit: Number of events to return (max 200)
            cursor: Pagination cursor from previous response

        Returns:
            Tuple of (events list, next cursor)
        """
        params = {"status": status, "limit": min(limit, 200)}
        if cursor:
            params["cursor"] = cursor

        data = await self._request("GET", "/events", params=params)
        events = data.get("events", [])
        next_cursor = data.get("cursor")

        return events, next_cursor

    async def get_all_events(
        self,
        status: str = "open",
        page_limit: int = 200,
        max_events: Optional[int] = None
    ) -> List[Dict]:
        """
        Get all events via cursor-based pagination.

        Args:
            status: Event status filter
            page_limit: Events per page (max 200)
            max_events: Maximum total events to fetch (None = all)

        Returns:
            List of all events
        """
        all_events: List[Dict] = []
        cursor: Optional[str] = None
        page_num = 0

        while True:
            page_num += 1
            events, next_cursor = await self.get_events(
                status=status,
                limit=page_limit,
                cursor=cursor
            )

            if not events:
                break

            all_events.extend(events)
            logger.debug(
                f"Fetched page {page_num}: {len(events)} events "
                f"(total: {len(all_events)})"
            )

            # Check max limit
            if max_events and len(all_events) >= max_events:
                all_events = all_events[:max_events]
                break

            # Check for more pages
            if not next_cursor:
                break

            cursor = next_cursor

        logger.info(f"✅ Fetched {len(all_events)} events total")
        return all_events

    # ========================================================================
    # MARKETS
    # ========================================================================

    async def get_markets(
        self,
        status: str = "open",
        limit: int = 1000,
        cursor: Optional[str] = None,
        event_ticker: Optional[str] = None
    ) -> Tuple[List[Dict], Optional[str]]:
        """
        Get a page of markets.

        Args:
            status: Market status (open, closed, settled)
            limit: Number of markets to return (max 1000)
            cursor: Pagination cursor
            event_ticker: Filter by specific event

        Returns:
            Tuple of (markets list, next cursor)
        """
        params = {"status": status, "limit": min(limit, 1000)}
        if cursor:
            params["cursor"] = cursor
        if event_ticker:
            params["event_ticker"] = event_ticker

        data = await self._request("GET", "/markets", params=params)
        markets = data.get("markets", [])
        next_cursor = data.get("cursor")

        return markets, next_cursor

    async def get_all_markets(
        self,
        status: str = "open",
        page_limit: int = 1000,
        max_markets: Optional[int] = None
    ) -> List[Dict]:
        """
        Get all markets via pagination.

        Args:
            status: Market status filter
            page_limit: Markets per page (max 1000)
            max_markets: Maximum total markets (None = all)

        Returns:
            List of all markets
        """
        all_markets: List[Dict] = []
        cursor: Optional[str] = None
        page_num = 0

        while True:
            page_num += 1
            markets, next_cursor = await self.get_markets(
                status=status,
                limit=page_limit,
                cursor=cursor
            )

            if not markets:
                break

            all_markets.extend(markets)
            logger.debug(
                f"Fetched page {page_num}: {len(markets)} markets "
                f"(total: {len(all_markets)})"
            )

            if max_markets and len(all_markets) >= max_markets:
                all_markets = all_markets[:max_markets]
                break

            if not next_cursor:
                break

            cursor = next_cursor

        logger.info(f"✅ Fetched {len(all_markets)} markets total")
        return all_markets

    async def get_markets_for_event(
        self,
        event_ticker: str,
        status: str = "open"
    ) -> List[Dict]:
        """
        Get all markets for a specific event.

        Args:
            event_ticker: Event ticker (e.g., 'PRES-2024')
            status: Market status filter

        Returns:
            List of markets for the event
        """
        try:
            markets, _ = await self.get_markets(
                status=status,
                event_ticker=event_ticker,
                limit=1000
            )
            return markets
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limited - wait and skip
                logger.warning(
                    f"Rate limit on event {event_ticker}, skipping"
                )
                await asyncio.sleep(2)
                return []
            raise

    async def get_all_markets_from_events(
        self,
        categories: Optional[List[str]] = None,
        max_events: Optional[int] = None,
        max_concurrent: int = 5
    ) -> List[Dict]:
        """
        Get markets from events in specific categories.

        This method enriches market data with event category and title.

        Args:
            categories: List of category names to filter by
            max_events: Maximum events to process (None = all)
            max_concurrent: Max concurrent API calls

        Returns:
            List of markets with added category and event_title fields
        """
        all_markets: List[Dict] = []

        # Fetch all open events
        logger.info("Fetching events...")
        events = await self.get_all_events(
            status="open",
            page_limit=200,
            max_events=max_events
        )

        # Filter by category if specified
        if categories:
            events = [e for e in events if e.get("category") in categories]
            logger.info(
                f"Filtered to {len(events)} events in categories: "
                f"{', '.join(categories)}"
            )

        if not events:
            logger.warning("No events found matching criteria")
            return []

        # Fetch markets for each event with concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)

        async def fetch_markets_with_semaphore(event: Dict) -> List[Dict]:
            """Fetch markets for one event with semaphore."""
            async with semaphore:
                try:
                    event_ticker = event["event_ticker"]
                    event_category = event.get("category")
                    event_title = event.get("title")

                    markets = await self.get_markets_for_event(event_ticker)

                    # Enrich markets with event data
                    for m in markets:
                        m["category"] = event_category
                        m["event_title"] = event_title

                    if markets:
                        logger.debug(
                            f"  • {event_ticker}: {len(markets)} markets"
                        )

                    return markets

                except Exception as e:
                    logger.error(
                        f"Error fetching markets for {event['event_ticker']}: {e}"
                    )
                    return []

        # Fetch all markets concurrently
        logger.info(f"Fetching markets from {len(events)} events...")
        results = await asyncio.gather(*[
            fetch_markets_with_semaphore(e) for e in events
        ])

        # Flatten results
        for market_list in results:
            all_markets.extend(market_list)

        logger.info(f"✅ Fetched {len(all_markets)} markets from events")
        return all_markets

    # ========================================================================
    # TRADES
    # ========================================================================

    async def get_trades(
        self,
        ticker: str,
        min_ts: Optional[int] = None,
        max_ts: Optional[int] = None,
        limit: int = 1000
    ) -> List[Dict]:
        """
        Get trade history for a market.

        Args:
            ticker: Market ticker (e.g., 'PRES-2024')
            min_ts: Minimum timestamp (Unix milliseconds)
            max_ts: Maximum timestamp (Unix milliseconds)
            limit: Maximum trades to return (max 1000)

        Returns:
            List of trades
        """
        params = {"ticker": ticker, "limit": min(limit, 1000)}
        if min_ts:
            params["min_ts"] = min_ts
        if max_ts:
            params["max_ts"] = max_ts

        data = await self._request("GET", "/markets/trades", params=params)
        trades = data.get("trades", [])

        return trades

    # ========================================================================
    # ORDERBOOK
    # ========================================================================

    async def get_orderbook(self, ticker: str) -> Dict:
        """
        Get current orderbook for a market.

        Args:
            ticker: Market ticker

        Returns:
            Orderbook data with yes/no bids and asks
        """
        data = await self._request("GET", f"/markets/{ticker}/orderbook")
        return data.get("orderbook", {})

    # ========================================================================
    # ACCOUNT (Optional)
    # ========================================================================

    async def get_account_limits(self) -> Dict:
        """
        Get your current API rate limits and usage.

        Useful for monitoring and tuning rate limits.

        Returns:
            Dictionary with limit information
        """
        data = await self._request("GET", "/account/limits")
        return data

    # ========================================================================
    # HEALTH & METRICS
    # ========================================================================

    async def health_check(self) -> bool:
        """
        Check if API is accessible.

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            await self._request("GET", "/events", params={"limit": 1})
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    def get_metrics(self) -> Optional[APIMetrics]:
        """
        Get API usage metrics.

        Returns:
            APIMetrics object or None if metrics disabled
        """
        return self.metrics

    def reset_metrics(self) -> None:
        """Reset API usage metrics."""
        if self.metrics:
            self.metrics = APIMetrics()

    def log_metrics(self) -> None:
        """Log current API usage metrics."""
        if not self.metrics:
            logger.info("Metrics tracking is disabled")
            return

        logger.info(
            f"API Metrics: "
            f"{self.metrics.total_requests} total requests, "
            f"{self.metrics.successful_requests} successful "
            f"({self.metrics.success_rate:.1%}), "
            f"{self.metrics.rate_limited_requests} rate limited, "
            f"avg response time: {self.metrics.avg_request_time:.2f}s"
        )

    def __repr__(self) -> str:
        return (
            f"KalshiAPI(strategy={self.rate_limit_strategy.value}, "
            f"max_rps={self.max_rps})"
        )


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

async def main():
    """Example usage of KalshiAPI."""

    # Initialize client
    kalshi = KalshiAPI(
        api_key_id="your_key_id",
        private_key_path="/path/to/private_key.pem",
        max_rps=10.0,
        redis_url="redis://localhost:6379/0"
    )

    # Health check
    is_healthy = await kalshi.health_check()
    print(f"API Health: {'✅' if is_healthy else '❌'}")

    # Fetch markets
    markets = await kalshi.get_markets(status="open", limit=10)
    print(f"\nFetched {len(markets)} markets")

    # Fetch markets from specific categories
    markets_by_category = await kalshi.get_all_markets_from_events(
        categories=["Politics", "Economics"],
        max_events=20
    )
    print(f"Fetched {len(markets_by_category)} markets from categories")

    # Get trades for a specific market
    if markets:
        ticker = markets[0]["ticker"]
        trades = await kalshi.get_trades(ticker, limit=100)
        print(f"\nFetched {len(trades)} trades for {ticker}")

    # Log metrics
    kalshi.log_metrics()


if __name__ == "__main__":
    # Run example
    asyncio.run(main())
