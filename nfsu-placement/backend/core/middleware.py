class SecurityHeadersMiddleware:
    """Adds a strict Content-Security-Policy and related headers to every API response.

    The API only ever returns JSON, so nothing is allowed to load or frame it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        if request.path.startswith("/api/"):
            response.setdefault("Cache-Control", "no-store")
        return response
