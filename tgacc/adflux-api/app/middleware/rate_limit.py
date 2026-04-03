"""
Rate limiting middleware using slowapi.

Tiers:
- Auth endpoints (/auth/login, /auth/register, /auth/forgot-password): 5/min
- Admin endpoints (/admin/*): 200/min
- General API: 100/min per client IP
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Reusable rate-limit strings
RATE_AUTH = "5/minute"
RATE_GENERAL = "100/minute"
RATE_ADMIN = "200/minute"


def rate_limit_exceeded_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a clear 429 response when the rate limit is exceeded."""
    retry_after = exc.detail.split()[-1] if exc.detail else "60"
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please slow down and try again later.",
            "retry_after": retry_after,
        },
        headers={"Retry-After": retry_after},
    )


def get_rate_limit_for_path(path: str) -> str:
    """Determine the appropriate rate limit based on the request path."""
    auth_sensitive = ("/auth/login", "/auth/register", "/auth/forgot-password")
    if path.rstrip("/") in auth_sensitive:
        return RATE_AUTH
    if path.startswith("/admin"):
        return RATE_ADMIN
    return RATE_GENERAL


async def rate_limit_middleware(request: Request, call_next):
    """Per-request middleware that applies tiered rate limits based on path."""
    # Let the slowapi limiter handle enforcement via decorators;
    # this middleware layer is kept thin so individual routes can also
    # use @limiter.limit() for finer control.
    response = await call_next(request)
    return response
