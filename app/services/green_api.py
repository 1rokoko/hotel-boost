"""
Green API HTTP Client with retry logic and rate limiting
"""

import asyncio
import time
import random
from typing import Optional, Dict, Any, Union, List
from datetime import datetime, timedelta
import httpx
import structlog
from contextlib import asynccontextmanager

from app.core.green_api_config import GreenAPIConfig, GreenAPIHotelConfig
from app.core.green_api_logging import get_green_api_logger, log_green_api_operation
from app.middleware.green_api_middleware import get_green_api_metrics
from app.schemas.green_api import (
    GreenAPIBaseRequest, GreenAPIBaseResponse, GreenAPIError,
    SendTextMessageRequest, SendFileRequest, SendLocationRequest,
    SendContactRequest, SendPollRequest, SetSettingsRequest,
    SendMessageResponse, GetSettingsResponse, GetStateInstanceResponse,
    MessageType, MessageStatus
)
from app.utils.circuit_breaker import get_circuit_breaker
from app.core.circuit_breaker_config import get_circuit_breaker_config, CircuitBreakerNames
from app.decorators.retry_decorator import retry_http_requests

logger = structlog.get_logger(__name__)


class RateLimiter:
    """Rate limiter for Green API requests"""
    
    def __init__(self, requests_per_minute: int, requests_per_second: int, burst_limit: int):
        self.requests_per_minute = requests_per_minute
        self.requests_per_second = requests_per_second
        self.burst_limit = burst_limit
        
        # Tracking
        self.minute_requests: List[float] = []
        self.second_requests: List[float] = []
        self.burst_count = 0
        self.last_reset = time.time()
        
        self._lock = asyncio.Lock()
    
    async def acquire(self) -> None:
        """Acquire rate limit permission"""
        async with self._lock:
            now = time.time()
            
            # Clean old requests
            self._clean_old_requests(now)
            
            # Check burst limit
            if self.burst_count >= self.burst_limit:
                wait_time = 1.0  # Wait 1 second for burst reset
                logger.warning("Rate limit burst exceeded, waiting", wait_time=wait_time)
                await asyncio.sleep(wait_time)
                self.burst_count = 0
            
            # Check per-second limit
            if len(self.second_requests) >= self.requests_per_second:
                wait_time = 1.0 - (now - self.second_requests[0])
                if wait_time > 0:
                    logger.warning("Per-second rate limit exceeded, waiting", wait_time=wait_time)
                    await asyncio.sleep(wait_time)
                    now = time.time()
                    self._clean_old_requests(now)
            
            # Check per-minute limit
            if len(self.minute_requests) >= self.requests_per_minute:
                wait_time = 60.0 - (now - self.minute_requests[0])
                if wait_time > 0:
                    logger.warning("Per-minute rate limit exceeded, waiting", wait_time=wait_time)
                    await asyncio.sleep(wait_time)
                    now = time.time()
                    self._clean_old_requests(now)
            
            # Record request
            self.minute_requests.append(now)
            self.second_requests.append(now)
            self.burst_count += 1
    
    def _clean_old_requests(self, now: float) -> None:
        """Clean old request timestamps"""
        # Clean minute requests (older than 60 seconds)
        self.minute_requests = [req for req in self.minute_requests if now - req < 60]
        
        # Clean second requests (older than 1 second)
        self.second_requests = [req for req in self.second_requests if now - req < 1]
        
        # Reset burst count every second
        if now - self.last_reset >= 1.0:
            self.burst_count = 0
            self.last_reset = now


class RetryHandler:
    """Handles retry logic with exponential backoff"""
    
    def __init__(self, config: GreenAPIConfig):
        self.max_retries = config.retry.max_retries
        self.base_delay = config.retry.base_delay
        self.max_delay = config.retry.max_delay
        self.exponential_base = config.retry.exponential_base
        self.jitter = config.retry.jitter
    
    async def execute_with_retry(self, func, *args, **kwargs):
        """Execute function with retry logic"""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except httpx.HTTPStatusError as e:
                last_exception = e
                
                # Don't retry on client errors (4xx) except rate limiting
                if 400 <= e.response.status_code < 500 and e.response.status_code != 429:
                    logger.error("Client error, not retrying", 
                               status_code=e.response.status_code, 
                               response=e.response.text)
                    raise
                
                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt, e.response.status_code)
                    logger.warning("Request failed, retrying", 
                                 attempt=attempt + 1, 
                                 max_retries=self.max_retries,
                                 delay=delay,
                                 status_code=e.response.status_code)
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max retries exceeded", 
                               attempts=attempt + 1,
                               status_code=e.response.status_code)
                    raise
            
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    delay = self._calculate_delay(attempt)
                    logger.warning("Network error, retrying", 
                                 attempt=attempt + 1,
                                 delay=delay,
                                 error=str(e))
                    await asyncio.sleep(delay)
                else:
                    logger.error("Max retries exceeded due to network error", 
                               attempts=attempt + 1,
                               error=str(e))
                    raise
        
        # This should never be reached, but just in case
        raise last_exception
    
    def _calculate_delay(self, attempt: int, status_code: Optional[int] = None) -> float:
        """Calculate delay for retry attempt"""
        # Special handling for rate limiting
        if status_code == 429:
            delay = min(self.base_delay * (2 ** attempt), 60.0)  # Cap at 60 seconds for rate limiting
        else:
            delay = min(self.base_delay * (self.exponential_base ** attempt), self.max_delay)
        
        # Add jitter to avoid thundering herd
        if self.jitter:
            delay *= (0.5 + random.random() * 0.5)
        
        return delay


class GreenAPIClient:
    """Green API HTTP client with retry logic and rate limiting"""
    
    def __init__(self, config: GreenAPIConfig):
        self.config = config
        self.rate_limiter = RateLimiter(
            config.rate_limit.requests_per_minute,
            config.rate_limit.requests_per_second,
            config.rate_limit.burst_limit
        )
        self.retry_handler = RetryHandler(config)
        self._client: Optional[httpx.AsyncClient] = None

        # Circuit breaker for reliability
        cb_config = get_circuit_breaker_config(CircuitBreakerNames.GREEN_API)
        self.circuit_breaker = get_circuit_breaker(CircuitBreakerNames.GREEN_API, cb_config)

        # Metrics
        self.request_count = 0
        self.error_count = 0
        self.last_request_time: Optional[datetime] = None

        # Green API specific logging and metrics
        self.green_api_logger = get_green_api_logger().with_instance(config.instance_id)
        self.metrics = get_green_api_metrics()
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def start(self) -> None:
        """Initialize HTTP client"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(**self.config.to_httpx_timeout()),
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
            )
            logger.info("Green API client started", instance_id=self.config.instance_id)
    
    async def close(self) -> None:
        """Close HTTP client"""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Green API client closed")
    
    @retry_http_requests(max_retries=3, base_delay=1.0)
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request with circuit breaker, rate limiting and retry"""
        if not self._client:
            await self.start()

        # Apply rate limiting
        await self.rate_limiter.acquire()

        # Build URL
        base_url = self.config.get_api_url()
        url = f"{base_url}/{endpoint}/{self.config.token}"

        # Prepare request
        request_data = {
            "method": method,
            "url": url,
            "params": params,
        }

        if data:
            request_data["json"] = data

        # Execute with circuit breaker protection
        async def make_http_request():
            self.last_request_time = datetime.utcnow()
            start_time = time.time()

            # Green API specific logging
            self.green_api_logger.log_request(method, url, data)

            if self.config.enable_detailed_logging:
                logger.info("Making Green API request",
                           method=method,
                           endpoint=endpoint,
                           url=url,
                           request_count=self.request_count)

                if self.config.log_request_body and data:
                    logger.debug("Request body", data=data)

            # Execute request
            response = await self._client.request(**request_data)
            response.raise_for_status()
            result = response.json()

            # Calculate response time and log
            response_time = (time.time() - start_time) * 1000
            self.green_api_logger.log_response(200, result, response_time)

            # Record metrics
            await self.metrics.record_request(
                instance_id=self.config.instance_id,
                response_time=response_time,
                status_code=200
            )

            if self.config.log_response_body:
                logger.debug("Response body", data=result)

            return result

        try:
            # Execute with circuit breaker
            result = await self.circuit_breaker.call(make_http_request)

            return result

        except Exception as e:
            self.error_count += 1

            # Log error
            self.green_api_logger.log_error(str(e))

            # Record error metrics
            status_code = getattr(e, 'response', {}).get('status_code', 0) if hasattr(e, 'response') else 0
            await self.metrics.record_request(
                instance_id=self.config.instance_id,
                response_time=0,
                status_code=status_code,
                error=str(e)
            )

            logger.error("Green API request failed",
                        method=method,
                        endpoint=endpoint,
                        error=str(e),
                        error_type=type(e).__name__)

            raise
            response_time = (time.time() - start_time) * 1000

            # Log error with Green API logger
            self.green_api_logger.log_error(e, f"{method} {endpoint}")

            # Record error metrics
            status_code = getattr(e, 'response', {}).get('status_code', 500) if hasattr(e, 'response') else 500
            await self.metrics.record_request(
                instance_id=self.config.instance_id,
                response_time=response_time,
                status_code=status_code,
                error=e
            )

            logger.error("Green API request failed",
                        method=method,
                        endpoint=endpoint,
                        error=str(e),
                        error_count=self.error_count)
            raise
    
    # API Methods
    async def send_text_message(self, request: SendTextMessageRequest) -> SendMessageResponse:
        """Send text message"""
        result = await self._make_request("POST", "sendMessage", request.dict())
        return SendMessageResponse(**result)
    
    async def send_file_by_url(self, request: SendFileRequest) -> SendMessageResponse:
        """Send file by URL"""
        result = await self._make_request("POST", "sendFileByUrl", request.dict())
        return SendMessageResponse(**result)
    
    async def send_location(self, request: SendLocationRequest) -> SendMessageResponse:
        """Send location"""
        result = await self._make_request("POST", "sendLocation", request.dict())
        return SendMessageResponse(**result)
    
    async def send_contact(self, request: SendContactRequest) -> SendMessageResponse:
        """Send contact"""
        result = await self._make_request("POST", "sendContact", request.dict())
        return SendMessageResponse(**result)
    
    async def send_poll(self, request: SendPollRequest) -> SendMessageResponse:
        """Send poll"""
        result = await self._make_request("POST", "sendPoll", request.dict())
        return SendMessageResponse(**result)
    
    async def get_settings(self) -> GetSettingsResponse:
        """Get instance settings"""
        result = await self._make_request("GET", "getSettings")
        return GetSettingsResponse(**result)
    
    async def set_settings(self, request: SetSettingsRequest) -> Dict[str, Any]:
        """Set instance settings"""
        return await self._make_request("POST", "setSettings", request.dict(exclude_none=True))
    
    async def get_state_instance(self) -> GetStateInstanceResponse:
        """Get instance state"""
        result = await self._make_request("GET", "getStateInstance")
        return GetStateInstanceResponse(**result)
    
    async def get_status_instance(self) -> Dict[str, Any]:
        """Get instance status"""
        return await self._make_request("GET", "getStatusInstance")
    
    async def receive_notification(self) -> Optional[Dict[str, Any]]:
        """Receive notification from queue"""
        try:
            result = await self._make_request("GET", "receiveNotification")
            return result if result else None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 204:  # No notifications
                return None
            raise
    
    async def delete_notification(self, receipt_id: str) -> Dict[str, Any]:
        """Delete notification from queue"""
        return await self._make_request("DELETE", f"deleteNotification/{receipt_id}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get client metrics"""
        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.request_count, 1),
            "last_request_time": self.last_request_time.isoformat() if self.last_request_time else None,
            "instance_id": self.config.instance_id
        }


@asynccontextmanager
async def green_api_client_context(config: GreenAPIConfig):
    """Async context manager for Green API client"""
    client = GreenAPIClient(config)
    try:
        await client.start()
        yield client
    finally:
        await client.close()


class GreenAPIClientPool:
    """Pool of Green API clients for multiple hotels"""

    def __init__(self):
        self._clients: Dict[str, GreenAPIClient] = {}
        self._configs: Dict[str, GreenAPIConfig] = {}
        self._lock = asyncio.Lock()

    async def get_client(self, hotel_id: str, config: GreenAPIConfig) -> GreenAPIClient:
        """Get or create client for hotel"""
        async with self._lock:
            if hotel_id not in self._clients:
                client = GreenAPIClient(config)
                await client.start()
                self._clients[hotel_id] = client
                self._configs[hotel_id] = config
                logger.info("Created new Green API client", hotel_id=hotel_id)

            return self._clients[hotel_id]

    async def remove_client(self, hotel_id: str) -> None:
        """Remove client for hotel"""
        async with self._lock:
            if hotel_id in self._clients:
                await self._clients[hotel_id].close()
                del self._clients[hotel_id]
                del self._configs[hotel_id]
                logger.info("Removed Green API client", hotel_id=hotel_id)

    async def close_all(self) -> None:
        """Close all clients"""
        async with self._lock:
            for hotel_id, client in self._clients.items():
                await client.close()
                logger.info("Closed Green API client", hotel_id=hotel_id)

            self._clients.clear()
            self._configs.clear()

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all clients"""
        return {
            hotel_id: client.get_metrics()
            for hotel_id, client in self._clients.items()
        }


# Global client pool instance
_client_pool = GreenAPIClientPool()


async def get_green_api_client(hotel_id: str, config: GreenAPIConfig) -> GreenAPIClient:
    """Get Green API client for hotel from pool"""
    return await _client_pool.get_client(hotel_id, config)


async def close_green_api_client(hotel_id: str) -> None:
    """Close Green API client for hotel"""
    await _client_pool.remove_client(hotel_id)


async def close_all_green_api_clients() -> None:
    """Close all Green API clients"""
    await _client_pool.close_all()


def get_all_green_api_metrics() -> Dict[str, Dict[str, Any]]:
    """Get metrics for all Green API clients"""
    return _client_pool.get_all_metrics()


# Factory function
def create_green_api_client(config: GreenAPIConfig) -> GreenAPIClient:
    """Create Green API client instance"""
    return GreenAPIClient(config)


# Export main components
__all__ = [
    'GreenAPIClient',
    'GreenAPIClientPool',
    'RateLimiter',
    'RetryHandler',
    'create_green_api_client',
    'green_api_client_context',
    'get_green_api_client',
    'close_green_api_client',
    'close_all_green_api_clients',
    'get_all_green_api_metrics'
]
