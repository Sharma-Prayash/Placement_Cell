import logging

from rest_framework.views import exception_handler

logger = logging.getLogger("nfsu")


def safe_exception_handler(exc, context):
    """DRF errors pass through; anything unexpected becomes a generic 500 with details only in the log."""
    response = exception_handler(exc, context)
    if response is None:
        logger.exception("Unhandled error in %s", context.get("view").__class__.__name__)
        from rest_framework.response import Response
        return Response({"detail": "Something went wrong on the server. The error has been logged."}, status=500)
    return response
