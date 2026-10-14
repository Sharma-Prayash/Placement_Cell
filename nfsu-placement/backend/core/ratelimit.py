"""Fixed-window rate limiting backed by the Django cache (Redis in production, so every worker shares counts).

Two properties matter for security:
- The client IP cannot be chosen by the client. X-Real-IP is honoured only when the TCP peer is a proxy listed
  in TRUSTED_PROXIES; otherwise a caller could send a fresh fake header with every request and never be limited.
- Cache keys are hashes, so identifiers such as email addresses or usernames are never stored in the cache.
A fixed window can let up to twice the limit through around a window boundary; the limits below allow for that.
"""
import hashlib
import ipaddress
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from rest_framework.response import Response


def _ip(value: str) -> str | None:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def client_ip(request) -> str:
    """The caller's address. Behind Nginx, list Nginx's address in TRUSTED_PROXIES and have it set X-Real-IP."""
    peer = _ip(request.META.get("REMOTE_ADDR", "")) or "unknown"
    if peer in settings.TRUSTED_PROXIES:
        forwarded = _ip(request.META.get("HTTP_X_REAL_IP", ""))
        if forwarded:
            return forwarded
    return peer


def _key(bucket: str) -> str:
    scope, _, ident = bucket.partition(":")
    return f"rl:{scope}:{hashlib.sha256(ident.encode()).hexdigest()[:40]}"


def hit(bucket: str, limit: int, window_seconds: int) -> bool:
    """Record one hit for `scope:identifier`; return True if the caller is still within the limit."""
    key = _key(bucket)
    if cache.add(key, 1, window_seconds):
        return True
    try:
        count = cache.incr(key)
    except ValueError:  # the window expired between add() and incr()
        cache.set(key, 1, window_seconds)
        count = 1
    return count <= limit


def too_many(detail: str, window_seconds: int) -> Response:
    """429 with Retry-After (the window length, an upper bound on the wait)."""
    r = Response({"detail": detail}, status=429)
    r["Retry-After"] = str(window_seconds)
    return r


def ratelimit(scope: str, limit: int, window_seconds: int, key=None):
    """Decorator for DRF view methods. `key(request)` defaults to the client IP."""

    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            ident = key(request) if key else client_ip(request)
            if not hit(f"{scope}:{ident}", limit, window_seconds):
                return too_many("Too many requests. Wait a while and try again.", window_seconds)
            return func(self, request, *args, **kwargs)

        return wrapper

    return decorator
