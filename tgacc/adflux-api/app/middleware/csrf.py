"""
Lightweight CSRF protection for state-changing endpoints.

Strategy:
- Require a custom header (X-CSRF-Token) on every mutating request
  (POST / PUT / PATCH / DELETE).
- The header value must match the token stored in the user's session cookie
  or be a known constant when using token-based (JWT) auth, where the
  presence of the custom header itself already proves the request was not
  triggered by a simple form submission (Double-Submit / Custom-Header
  pattern).
"""

import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_HEADER = "X-CSRF-Token"
CSRF_COOKIE = "csrf_token"


def generate_csrf_token() -> str:
    """Return a cryptographically secure CSRF token."""
    return secrets.token_urlsafe(32)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Enforce CSRF protection on state-changing endpoints.

    For token-authenticated APIs the mere presence of the custom header
    is sufficient (browsers do not send custom headers in cross-origin
    simple requests).  If a csrf_token cookie is set, its value must
    match the header for an extra layer of defence.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in SAFE_METHODS:
            response = await call_next(request)
            # Set a CSRF cookie if one isn't present yet
            if CSRF_COOKIE not in request.cookies:
                token = generate_csrf_token()
                response.set_cookie(
                    CSRF_COOKIE,
                    token,
                    httponly=False,  # JS needs to read it
                    samesite="strict",
                    secure=True,
                )
            return response

        # Mutating request — require the custom header
        header_token = request.headers.get(CSRF_HEADER)
        if not header_token:
            return JSONResponse(
                status_code=403,
                content={"detail": "Missing CSRF token header"},
            )

        # If a cookie exists, verify double-submit match
        cookie_token = request.cookies.get(CSRF_COOKIE)
        if cookie_token and not secrets.compare_digest(header_token, cookie_token):
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token mismatch"},
            )

        return await call_next(request)
