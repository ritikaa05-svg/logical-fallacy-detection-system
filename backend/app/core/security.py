"""
Security and input sanitization middleware for LogiScan.
Implements rate limiting, prompt injection defense, and input validation.
"""

import hashlib
import logging
import re
import time
from collections import OrderedDict

import redis as redis_lib
import tiktoken
from fastapi import HTTPException, Request, status

from backend.app.config import settings

logger = logging.getLogger(__name__)

# Initialize tokenizer for tiktoken (used by GPT models, but works for estimation)
TOKENIZER = tiktoken.get_encoding("cl100k_base")

# Prompt injection patterns to detect and neutralize
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above|aforementioned)\s+(instructions?|prompts?|directives?)",
    r"(you\s+are|act\s+as|pretend\s+to\s+be|roleplay\s+as)\s+(now\s+)?(a\s+)?(different|new|another)",
    r"(system\s*[:=]|assistant\s*[:=]|user\s*[:=])\s*",
    r"<\|im_start\|>|<\|im_end\|>",
    r"\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>",
    r"override\s+(the\s+)?system\s+prompt",
    r"bypass\s+(the\s+)?(safety|security|content)\s+(filter|restrictions?)",
]


class RateLimiter:
    """
    Sliding window rate limiter backed by Redis sorted sets with in-memory fallback.
    """

    def __init__(
        self,
        max_requests: int = 60,
        window_seconds: int = 60,
        authenticated_max: int | None = None,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.authenticated_max = authenticated_max
        self._clients: dict[str, list[float]] = OrderedDict()
        self._cleanup_interval = 300
        self._last_cleanup = time.time()
        self._redis_available = False
        self._redis = None
        self._prefix = "ratelimit:"
        self._max_fallback_entries = 10000
        self._last_reconnect_attempt = 0.0
        self._reconnect_interval = 30.0

        try:
            self._redis = redis_lib.Redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=2,
                socket_timeout=2,
                decode_responses=True,
            )
            self._redis.ping()
            self._redis_available = True
            logger.info("RateLimiter: Redis connected successfully.")
        except Exception as e:
            self._redis_available = False
            self._redis = None
            logger.warning(f"RateLimiter: Redis unavailable, using in-memory fallback: {e}")

    def _try_reconnect(self) -> None:
        now = time.time()
        if now - self._last_reconnect_attempt < self._reconnect_interval:
            return
        self._last_reconnect_attempt = now
        try:
            self._redis = redis_lib.Redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=2,
                socket_timeout=2,
                decode_responses=True,
            )
            self._redis.ping()
            self._redis_available = True
            logger.info("RateLimiter: Redis reconnected.")
        except Exception:
            self._redis_available = False
            self._redis = None

    def get_limit(self, authenticated: bool = False) -> int:
        if authenticated and self.authenticated_max is not None:
            return self.authenticated_max
        return self.max_requests

    def _cleanup_old_entries(self) -> None:
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        cutoff = now - self.window_seconds
        expired = []
        for client_ip, timestamps in list(self._clients.items()):
            self._clients[client_ip] = [t for t in timestamps if t > cutoff]
            if not self._clients[client_ip]:
                expired.append(client_ip)
        for client_ip in expired:
            del self._clients[client_ip]
        # Evict oldest entries when fallback exceeds capacity
        while len(self._clients) > self._max_fallback_entries:
            self._clients.popitem(last=False)  # type: ignore[call-arg]
        self._last_cleanup = now

    def is_allowed(self, client_ip: str, authenticated: bool = False) -> tuple[bool, int, int]:
        max_r = self.get_limit(authenticated)
        now = time.time()
        cutoff = now - self.window_seconds

        if self._redis_available and self._redis is not None:
            try:
                self._try_reconnect()
                key = f"{self._prefix}{client_ip}"
                self._redis.zremrangebyscore(key, "-inf", cutoff)
                count = self._redis.zcount(key, cutoff, "+inf")

                if int(count) >= max_r:
                    oldest = self._redis.zrange(key, 0, 0, withscores=True)
                    reset_seconds = self.window_seconds
                    if oldest:
                        reset_ts = oldest[0][1] + self.window_seconds
                        reset_seconds = max(1, int(reset_ts - now))
                    return False, 0, reset_seconds

                member = f"{client_ip}:{time.time_ns()}"
                self._redis.zadd(key, {member: now})
                self._redis.expire(key, self.window_seconds * 2)
                remaining = max_r - int(count) - 1
                oldest = self._redis.zrange(key, 0, 0, withscores=True)
                reset_seconds = self.window_seconds
                if oldest:
                    reset_ts = oldest[0][1] + self.window_seconds
                    reset_seconds = max(1, int(reset_ts - now))
                return True, remaining, reset_seconds
            except Exception:
                self._redis_available = False
                self._try_reconnect()

        self._cleanup_old_entries()
        timestamps = self._clients.get(client_ip, [])
        self._clients[client_ip] = [t for t in timestamps if t > cutoff]

        if len(self._clients[client_ip]) >= max_r:
            reset_seconds = max(1, int(self._clients[client_ip][0] + self.window_seconds - now))
            return False, 0, reset_seconds

        self._clients[client_ip].append(now)
        remaining = max_r - len(self._clients[client_ip])
        reset_seconds = self.window_seconds
        if self._clients[client_ip]:
            reset_seconds = max(1, int(self._clients[client_ip][0] + self.window_seconds - now))
        return True, remaining, reset_seconds

    def get_remaining(self, client_ip: str) -> int:
        max_r = self.max_requests
        now = time.time()
        cutoff = now - self.window_seconds

        if self._redis_available and self._redis is not None:
            try:
                self._try_reconnect()
                key = f"{self._prefix}{client_ip}"
                self._redis.zremrangebyscore(key, "-inf", cutoff)
                count = self._redis.zcount(key, cutoff, "+inf")
                return max(0, max_r - int(count))
            except Exception:
                self._redis_available = False
                self._try_reconnect()

        self._cleanup_old_entries()
        timestamps = self._clients.get(client_ip, [])
        self._clients[client_ip] = [t for t in timestamps if t > cutoff]
        return max(0, max_r - len(self._clients[client_ip]))

    def get_reset(self, client_ip: str) -> int:
        now = time.time()
        cutoff = now - self.window_seconds

        if self._redis_available and self._redis is not None:
            try:
                self._try_reconnect()
                key = f"{self._prefix}{client_ip}"
                oldest = self._redis.zrange(key, 0, 0, withscores=True)
                if oldest:
                    reset_ts = oldest[0][1] + self.window_seconds
                    return max(1, int(reset_ts - now))
                return self.window_seconds
            except Exception:
                self._redis_available = False
                self._try_reconnect()

        self._cleanup_old_entries()
        timestamps = self._clients.get(client_ip, [])
        self._clients[client_ip] = [t for t in timestamps if t > cutoff]
        if self._clients[client_ip]:
            return max(1, int(self._clients[client_ip][0] + self.window_seconds - now))
        return self.window_seconds


# Global rate limiter instance
rate_limiter = RateLimiter(
    max_requests=settings.RATE_LIMIT_DEFAULT,
    window_seconds=60,
    authenticated_max=settings.RATE_LIMIT_AUTHENTICATED,
)


def sanitize_input(text: str) -> str:
    """
    Sanitize input text to defend against prompt injection attacks.

    Strategy:
    1. Detect and neutralize known injection patterns
    2. Normalize whitespace
    3. Remove control characters
    4. Truncate to token limit

    Args:
        text: Raw input text from user

    Returns:
        Sanitized text safe for model processing
    """
    if not text or not text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Input text cannot be empty.")

    original_text = text

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text.strip())

    # Remove non-printable control characters (except common ones)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Detect and neutralize injection patterns
    injection_detected = False
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            injection_detected = True
            # Replace the pattern with a harmless placeholder
            text = re.sub(pattern, "[REDACTED]", text, flags=re.IGNORECASE)
            logger.warning(f"Prompt injection pattern detected and neutralized: {pattern}")

    if injection_detected:
        logger.warning(
            f"Injection attempt detected. Original length: {len(original_text)}, Sanitized length: {len(text)}"
        )

    # Enforce token limit
    tokens = TOKENIZER.encode(text)
    if len(tokens) > settings.MAX_INPUT_TOKENS:
        tokens = tokens[: settings.MAX_INPUT_TOKENS]
        text = TOKENIZER.decode(tokens)
        logger.info(f"Input truncated to {settings.MAX_INPUT_TOKENS} tokens.")

    return text


def validate_input_length(text: str) -> int:
    """
    Validate input length and return token count.

    Args:
        text: Input text to validate

    Returns:
        Number of tokens in the text

    Raises:
        HTTPException: If input exceeds token limit
    """
    token_count = len(TOKENIZER.encode(text))

    if token_count > settings.MAX_INPUT_TOKENS:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Input exceeds maximum of {settings.MAX_INPUT_TOKENS} tokens. "
            f"Current count: {token_count}. Please shorten your text.",
        )

    return token_count


def generate_cache_key(text: str) -> str:
    """
    Generate a deterministic cache key for input text.
    Uses SHA-256 for collision resistance.

    Args:
        text: Sanitized input text

    Returns:
        Hex-encoded SHA-256 hash
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def rate_limit_middleware(request: Request) -> None:
    """
    FastAPI middleware dependency for rate limiting.

    Usage:
        @app.post("/analyze", dependencies=[Depends(rate_limit_middleware)])
    """
    client_ip = request.client.host if request.client else "unknown"
    authenticated = getattr(request.state, "authenticated", False)

    allowed, remaining, reset_seconds = rate_limiter.is_allowed(client_ip, authenticated=authenticated)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Retry in {reset_seconds} seconds.",
            headers={"Retry-After": str(reset_seconds)},
        )

    # Add rate limit headers to response (handled in middleware.py)
    request.state.rate_limit_remaining = remaining
    request.state.rate_limit_reset = reset_seconds
    request.state.rate_limit_limit = rate_limiter.get_limit(authenticated)
