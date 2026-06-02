import httpx
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Tuple
import os

from configs.logfire_config import setup_logger

logger = setup_logger(__name__)

# Get the Twitter service URL from environment variable or use default
TWITTER_SERVICE_URL = os.getenv("TWITTER_SERVICE_URL", "http://localhost:8001")

class TwitterServiceClient:
    """
    Client for the Twitter service API.
    
    This client communicates with the Twitter service microservice to fetch Twitter data.
    It supports both synchronous (legacy) and asynchronous (queue-based) modes with
    automatic fallback and intelligent request handling.
    """
    
    def __init__(self, base_url: str = TWITTER_SERVICE_URL, timeout: float = 30.0, max_retries: int = 3, 
                 use_async_mode: bool = True, max_poll_time: int = 600):
        """
        Initialize the Twitter service client.
        
        Args:
            base_url: Base URL for the Twitter service API
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts for failed requests
            use_async_mode: Whether to use async queue endpoints by default
            max_poll_time: Maximum time to poll for async results (seconds)
        """
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.use_async_mode = use_async_mode
        self.max_poll_time = max_poll_time
        self.poll_interval = 1.0  # seconds between polls
        
    async def _make_request(self, method: str, endpoint: str, params: Optional[Dict[str, Any]] = None, 
                           json_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a request to the Twitter service API with retries.
        
        Args:
            method: HTTP method (GET, POST)
            endpoint: API endpoint path
            params: Query parameters
            json_data: JSON data for POST requests
            
        Returns:
            Response data
            
        Raises:
            Exception: If all retries fail
        """
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    url = f"{self.base_url}{endpoint}"
                    logger.info(f"Making {method} request to Twitter service: {url} with params {params}")
                    
                    if method.upper() == "POST":
                        response = await client.post(url, params=params, json=json_data)
                    else:
                        response = await client.get(url, params=params)
                    
                    response.raise_for_status()
                    return response.json()
            except (httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ReadError, httpx.ConnectError) as e:
                if attempt == self.max_retries - 1:
                    logger.error(f"Failed to connect to Twitter service at {self.base_url} after {self.max_retries} attempts: {str(e)}")
                    raise
                
                # Exponential backoff for retries
                backoff_time = 0.5 * (2 ** attempt)
                logger.warning(f"Request to Twitter service failed, retrying in {backoff_time:.2f}s (attempt {attempt+1}/{self.max_retries})")
                await asyncio.sleep(backoff_time)
    
    async def _queue_request_and_poll(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make an async queue request and poll for results.
        
        Args:
            endpoint: POST endpoint for queuing the request
            params: Query parameters
            
        Returns:
            Final result data
            
        Raises:
            Exception: If request fails or polling times out
        """
        # Queue the request
        queue_response = await self._make_request("POST", endpoint, params)
        request_id = queue_response["request_id"]
        
        logger.info(f"Queued request {request_id}, estimated wait: {queue_response['estimated_wait_time']}")
        
        # Poll for completion
        start_time = time.time()
        while time.time() - start_time < self.max_poll_time:
            status_response = await self._make_request("GET", f"/status/{request_id}")
            status = status_response["status"]
            
            if status == "completed":
                # Get the result
                result = status_response.get("result")
                if result:
                    logger.info(f"Request {request_id} completed successfully")
                    return result
                else:
                    # Try to get result from the result endpoint
                    result_response = await self._make_request("GET", f"/result/{request_id}")
                    return result_response
                    
            elif status == "failed":
                error = status_response.get("error", "Unknown error")
                logger.error(f"Request {request_id} failed: {error}")
                raise Exception(f"Twitter service request failed: {error}")
                
            elif status == "timeout":
                logger.error(f"Request {request_id} timed out")
                raise Exception("Twitter service request timed out")
            
            # Wait before polling again
            await asyncio.sleep(self.poll_interval)
        
        # Timeout reached
        logger.error(f"Polling timeout reached for request {request_id}")
        raise Exception(f"Polling timeout reached for request {request_id}")
    
    async def _fetch_with_fallback(self, async_endpoint: str, sync_endpoint: str, 
                                  params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Fetch data using async endpoint with fallback to sync endpoint.
        
        Args:
            async_endpoint: Async queue-based endpoint
            sync_endpoint: Synchronous legacy endpoint
            params: Query parameters
            
        Returns:
            Response data
        """
        if self.use_async_mode:
            try:
                return await self._queue_request_and_poll(async_endpoint, params)
            except Exception as e:
                logger.warning(f"Async request failed, falling back to sync: {str(e)}")
                # Fall back to sync mode
                return await self._make_request("GET", sync_endpoint, params)
        else:
            # Use sync mode directly
            return await self._make_request("GET", sync_endpoint, params)
            
    async def fetch_user_info(self, username: str) -> Dict[str, Any]:
        """
        Fetch user information for a Twitter username.
        
        Args:
            username: Twitter username
            
        Returns:
            User information dictionary
        """
        try:
            response = await self._fetch_with_fallback(
                f"/twitter/user/{username}",
                f"/twitter/user/{username}/sync"
            )
            return response.get("user_info", response)
        except Exception as e:
            logger.error(f"Error fetching user info for {username}: {str(e)}")
            return {}
            
    async def fetch_twitter_data(self, username: str, from_date: Optional[int] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Fetch Twitter data (user info, tweets, retweets) for a username.
        
        Args:
            username: Twitter username
            from_date: Optional timestamp to filter tweets from
            
        Returns:
            Tuple of (user_info, tweets, retweets)
        """
        try:
            params = {}
            if from_date:
                params["from_date"] = from_date
                
            response = await self._fetch_with_fallback(
                f"/twitter/data/{username}",
                f"/twitter/data/{username}/sync",
                params
            )
            
            return (
                response.get("user_info", {}),
                response.get("tweets", []),
                response.get("retweets", [])
            )
        except Exception as e:
            logger.error(f"Error fetching Twitter data for {username}: {str(e)}")
            return {}, [], []
            
    async def get_first_hundred_tweets(self, username: str, user_id: str) -> Tuple[List[Dict[str, Any]], str]:
        """
        Get the first batch of tweets for a user.
        
        Args:
            username: Twitter username
            user_id: Twitter user ID
            
        Returns:
            Tuple of (tweets list, continuation token)
        """
        try:
            params = {"user_id": user_id}
            
            if self.use_async_mode:
                try:
                    response = await self._queue_request_and_poll(f"/twitter/tweets/{username}", params)
                except Exception as e:
                    logger.warning(f"Async tweets request failed, using legacy mode: {str(e)}")
                    # This endpoint doesn't have a sync version, so we'll construct one
                    # For now, we'll just use the sync data endpoint and extract tweets
                    twitter_data = await self._make_request("GET", f"/twitter/data/{username}/sync")
                    return twitter_data.get("tweets", [])[:100], ""
            else:
                # Legacy mode - use the sync data endpoint 
                twitter_data = await self._make_request("GET", f"/twitter/data/{username}/sync")
                return twitter_data.get("tweets", [])[:100], ""
            
            return (
                response.get("tweets", []),
                response.get("continuation_token", "")
            )
        except Exception as e:
            logger.error(f"Error fetching first hundred tweets for {username}: {str(e)}")
            return [], ""
            
    async def fetch_continuation_tweets(
        self, 
        username: str, 
        user_id: str, 
        continuation_token: str, 
        no_of_tweets: int = 100
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Fetch additional tweets using a continuation token.
        
        Args:
            username: Twitter username
            user_id: Twitter user ID
            continuation_token: Token from previous request
            no_of_tweets: Number of tweets to fetch
            
        Returns:
            Tuple of (tweets list, new continuation token)
        """
        try:
            params = {
                "user_id": user_id,
                "continuation_token": continuation_token,
                "limit": no_of_tweets
            }
            
            if self.use_async_mode:
                try:
                    response = await self._queue_request_and_poll(f"/twitter/tweets/continuation/{username}", params)
                    return (
                        response.get("tweets", []),
                        response.get("continuation_token", "")
                    )
                except Exception as e:
                    logger.warning(f"Async continuation tweets request failed: {str(e)}")
                    # Fallback: return empty as continuation doesn't have a sync equivalent
                    return [], ""
            else:
                # Legacy mode - return empty as this is an advanced feature
                logger.warning("Continuation tweets not available in sync mode")
                return [], ""
            
        except Exception as e:
            logger.error(f"Error fetching continuation tweets for {username}: {str(e)}")
            return [], ""
    
    async def get_metrics(self) -> Dict[str, Any]:
        """
        Get service metrics and monitoring information.
        
        Returns:
            Service metrics
        """
        try:
            return await self._make_request("GET", "/metrics")
        except Exception as e:
            logger.error(f"Error fetching Twitter service metrics: {str(e)}")
            return {"error": str(e)}
            
    async def check_health(self) -> Dict[str, Any]:
        """
        Check the health of the Twitter service.
        
        Returns:
            Health status information
        """
        try:
            return await self._make_request("GET", "/health")
        except Exception as e:
            logger.error(f"Error checking Twitter service health: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def set_async_mode(self, enabled: bool):
        """Enable or disable async mode."""
        self.use_async_mode = enabled
        logger.info(f"Twitter service client async mode {'enabled' if enabled else 'disabled'}")
    
    def set_polling_config(self, max_poll_time: int, poll_interval: float):
        """Update polling configuration."""
        self.max_poll_time = max_poll_time
        self.poll_interval = poll_interval
        logger.info(f"Updated polling config: max_time={max_poll_time}s, interval={poll_interval}s")

# Create a singleton instance
_twitter_service_client = None

def get_twitter_service_client() -> TwitterServiceClient:
    """Get the Twitter service client singleton."""
    global _twitter_service_client
    if _twitter_service_client is None:
        # Check environment variables for configuration
        use_async = os.getenv("TWITTER_SERVICE_ASYNC_MODE", "true").lower() in ("true", "1", "yes")
        max_poll_time = int(os.getenv("TWITTER_SERVICE_MAX_POLL_TIME", "600"))
        
        _twitter_service_client = TwitterServiceClient(
            use_async_mode=use_async,
            max_poll_time=max_poll_time,timeout=60.0,  # Increase timeout
            max_retries=5 
        )
    return _twitter_service_client

# Export the functions with the same interface as the original Twitter service
async def fetch_user_info(username: str) -> Dict[str, Any]:
    """Fetch user information for a Twitter username."""
    client = get_twitter_service_client()
    return await client.fetch_user_info(username)

async def fetch_twitter_data(username: str, from_date: Optional[int] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Fetch Twitter data for a username."""
    client = get_twitter_service_client()
    return await client.fetch_twitter_data(username, from_date)

async def get_first_hundred_tweets(username: str, user_id: str) -> Tuple[List[Dict[str, Any]], str]:
    """Get the first batch of tweets for a user."""
    client = get_twitter_service_client()
    return await client.get_first_hundred_tweets(username, user_id)

async def fetch_continuation_tweets(username: str, user_id: str, continuation_token: str, no_of_tweets: int = 100) -> Tuple[List[Dict[str, Any]], str]:
    """Fetch continuation tweets using a token."""
    client = get_twitter_service_client()
    return await client.fetch_continuation_tweets(username, user_id, continuation_token, no_of_tweets) 