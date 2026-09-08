"""
FastAPI Middleware
Error handling, request timing, CORS configuration, rate limit headers, and request ID tracking.
"""

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.config import settings

logger = logging.getLogger(__name__)

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Add X-Process-Time header to all responses for performance monitoring.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()

        response = await call_next(request)

        process_time = (time.perf_counter() - start_time) * 1000
        response.headers["X-Process-Time"] = f"{process_time:.1f}ms"

        return response


class RateLimitHeaderMiddleware(BaseHTTPMiddleware):
    """
    Add rate limit headers from request state to response.
    Works in conjunction with the rate_limit_middleware dependency.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Add rate limit headers if available
        if hasattr(request.state, "rate_limit_remaining"):
            response.headers["X-RateLimit-Remaining"] = str(request.state.rate_limit_remaining)
            response.headers["X-RateLimit-Limit"] = str(request.state.rate_limit_limit)
            response.headers["X-RateLimit-Reset"] = str(request.state.rate_limit_reset)

        return response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Generate or forward a UUID request ID per request.
    Stores the ID in request.state.request_id and the X-Request-ID response header.
    Makes the request ID accessible in logging via request_id_var context var.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path.startswith("/assets"):
            return await call_next(request)
        rid = request.headers.get("X-Request-ID", uuid.uuid4().hex)
        request.state.request_id = rid
        token = request_id_var.set(rid)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            request_id_var.reset(token)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security headers to all responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"

        return response


def setup_middleware(app: FastAPI) -> None:
    """
    Configure all middleware for the FastAPI application.

    Args:
        app: FastAPI application instance
    """

    # CORS: Allow Chrome extension and Streamlit frontend.
    # NOTE: Starlette's allow_origins matches exact strings only — a literal
    # "chrome-extension://*" never matches real extension origins, so extension
    # requests are matched via allow_origin_regex instead.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_origin_regex=settings.ALLOWED_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=[
            "X-Process-Time",
            "X-RateLimit-Remaining",
            "X-RateLimit-Limit",
            "X-RateLimit-Reset",
            "X-Request-ID",
        ],
    )

    # Custom middleware (added in reverse order of execution)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitHeaderMiddleware)
    app.add_middleware(TimingMiddleware)

    logger.info("Middleware configured: CORS, Timing, RateLimit, SecurityHeaders, RequestID.")


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Register global exception handlers for graceful error responses.

    Args:
        app: FastAPI application instance
    """

    async def timeout_error_handler(request: Request, exc: TimeoutError) -> JSONResponse:
        """Handle timeout errors (registered BEFORE generic Exception to avoid dead code)."""
        logger.error(f"Timeout error: {exc}")
        return JSONResponse(
            status_code=504,
            content={
                "error": "Request timeout",
                "detail": "The analysis took too long. Please try again with shorter text.",
            },
        )

    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Handle validation errors."""
        logger.warning(f"Validation error: {exc}")
        return JSONResponse(
            status_code=400,
            content={
                "error": "Validation error",
                "detail": str(exc),
            },
        )

    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all exception handler for unhandled errors."""
        logger.error(
            f"Unhandled exception: {type(exc).__name__}: {exc}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc) if settings.DEBUG else "An unexpected error occurred.",
                "type": type(exc).__name__,
            },
        )

    app.add_exception_handler(TimeoutError, timeout_error_handler)
    app.add_exception_handler(ValueError, value_error_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    logger.info("Exception handlers registered.")
