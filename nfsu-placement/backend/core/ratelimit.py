"""Fixed-window rate limiting backed by the Django cache (Redis in production)."""
from functools import wraps

from django.core.cache import cache
from rest_framework.response import Response


def client_ip(request):
    # Behind Nginx, configure it to set X-Real-IP; never trust X-Forwarded-For blindly.
    return request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "unknown")


def hit(bucket: str, limit: int, window_seconds: int) -> bool:
    """Record one hit; return True if the caller is still within the limit."""
    key = f"rl:{bucket}"
    added = cache.add(key, 1, window_seconds)
    if added:
        return True
    try:
        count = cache.incr(key)
    except ValueError:
        cache.set(key, 1, window_seconds)
        count = 1
    return count <= limit


def ratelimit(scope: str, limit: int, window_seconds: int, key=None):
    """Decorator for DRF view methods. `key(request)` defaults to the client IP."""

    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            ident = key(request) if key else client_ip(request)
            if not hit(f"{scope}:{ident}", limit, window_seconds):
                return Response({"detail": "Too many requests. Wait a while and try again."}, status=429)
            return func(self, request, *args, **kwargs)

        return wrapper

    return decorator
