"""
Middleware for Authentication and Rate Limiting
"""

import logging
import time
from typing import Optional, Dict
from datetime import datetime, timedelta
import os

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    JWT authentication middleware.

    In production, this validates JWT tokens from Auth0, Firebase, etc.
    For now, extracts user context (TODO: implement JWT validation)
    """

    async def dispatch(self, request: Request, call_next):
        """Process request through authentication"""
        # Skip auth for health endpoints
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization", "")
        token = None

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

        # TODO: Validate JWT token
        # user_id = validate_jwt_token(token)
        # For now, accept all requests and use user_id from query param
        user_id = request.query_params.get("user_id", "guest")

        # Attach user context to request
        request.state.user_id = user_id
        request.state.auth_token = token

        logger.debug(f"Auth: user_id={user_id}")

        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"Auth error: {e}")
            return JSONResponse(
                status_code=401,
                content={"error": "Authentication failed"}
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using in-memory sliding window counter.

    Production: Use Redis for distributed rate limiting.
    For now: Simple in-process rate limiter.
    """

    def __init__(self, app):
        super().__init__(app)
        self.requests: Dict[str, list] = {}  # user_id -> [timestamps]
        self.limits = {
            "/api/save-link": 100,     # 100 requests per minute
            "/api/search": 20,         # 20 requests per minute
            "/api/links": 30,          # 30 requests per minute
            "default": 100             # 100 requests per minute for others
        }
        self.window_size = 60  # 1 minute window

    async def dispatch(self, request: Request, call_next):
        """Check rate limits before processing request"""
        # Skip rate limiting for health endpoints
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)

        user_id = getattr(request.state, "user_id", "guest")
        path = request.url.path
        now = time.time()

        # Get rate limit for this endpoint
        limit = self.limits.get(path, self.limits["default"])

        # Clean old requests (older than window_size)
        if user_id not in self.requests:
            self.requests[user_id] = []

        self.requests[user_id] = [
            ts for ts in self.requests[user_id]
            if now - ts < self.window_size
        ]

        # Check if limit exceeded
        if len(self.requests[user_id]) >= limit:
            logger.warning(f"Rate limit exceeded: {user_id} on {path}")
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"},
                headers={"Retry-After": str(self.window_size)}
            )

        # Record this request
        self.requests[user_id].append(now)

        response = await call_next(request)
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all HTTP requests and responses"""

    async def dispatch(self, request: Request, call_next):
        """Log request/response"""
        start_time = time.time()
        user_id = getattr(request.state, "user_id", "unknown")

        logger.info(
            f"{request.method} {request.url.path} "
            f"(user={user_id})"
        )

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            logger.info(
                f"{response.status_code} {request.url.path} "
                f"({duration:.2f}s)"
            )

            return response
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Error on {request.url.path}: {e} ({duration:.2f}s)"
            )
            raise


# ============================================================================
# TOKEN VALIDATION (Placeholder - implement with your auth provider)
# ============================================================================

def validate_jwt_token(token: Optional[str]) -> Optional[str]:
    """
    Validate JWT token and extract user ID.

    TODO: Implement with your auth provider (Auth0, Firebase, etc.)

    Example with Auth0:
        import jwt
        from functools import lru_cache

        @lru_cache(maxsize=100)
        def get_auth0_public_key():
            url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
            response = requests.get(url)
            return response.json()

        try:
            decoded = jwt.decode(
                token,
                get_auth0_public_key(),
                algorithms=["RS256"],
                audience=AUTH0_AUDIENCE
            )
            return decoded["sub"]  # Auth0 user ID
        except jwt.InvalidTokenError:
            return None

    Args:
        token: JWT token string

    Returns:
        User ID if valid, None otherwise
    """
    if not token:
        return None

    try:
        # TODO: Implement actual JWT validation
        # For now, accept any token
        logger.debug("JWT validation not implemented (TODO)")
        return "test-user"

    except Exception as e:
        logger.error(f"Token validation failed: {e}")
        return None


# ============================================================================
# RATE LIMIT CHECKER
# ============================================================================

def check_api_quota(user_id: str, db=None) -> tuple[bool, str]:
    """
    Check if user has exceeded API quota.

    Args:
        user_id: User ID
        db: Database session

    Returns:
        (is_allowed: bool, message: str)
    """
    # TODO: Implement with actual database queries
    # Check user's API usage against plan limits

    return True, "OK"
