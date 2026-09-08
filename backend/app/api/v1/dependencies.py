"""
FastAPI Dependencies
Reusable dependency injection for API v1 endpoints.
"""

from fastapi import Request


async def get_client_ip(request: Request) -> str:
    """
    Extract client IP from request, respecting forwarded headers.

    Args:
        request: FastAPI Request object

    Returns:
        Client IP address string
    """
    # Check for X-Forwarded-For header (for reverse proxy setups)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # Check for X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct client host
    if request.client:
        return request.client.host

    return "unknown"
