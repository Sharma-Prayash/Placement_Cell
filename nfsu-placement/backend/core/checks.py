"""`manage.py check --deploy` warnings for settings that silently weaken rate limiting."""
from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.security, deploy=True)
def rate_limit_settings(app_configs, **kwargs):
    issues = []
    backend = settings.CACHES["default"]["BACKEND"]
    if backend.endswith("LocMemCache"):
        issues.append(Warning(
            "Rate limits and lockouts use a per-process memory cache, so each worker counts separately.",
            hint="Set REDIS_URL so every worker shares the same counters.", id="nfsu.W001"))
    if not settings.TRUSTED_PROXIES:
        issues.append(Warning(
            "TRUSTED_PROXIES is empty. Behind Nginx every request would appear to come from the proxy, so all users "
            "would share one rate-limit bucket.",
            hint="Set TRUSTED_PROXIES to the proxy's address and have it send X-Real-IP $remote_addr.", id="nfsu.W002"))
    return issues
