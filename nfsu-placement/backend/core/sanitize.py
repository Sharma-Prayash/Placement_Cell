import bleach

ALLOWED_TAGS = ["p", "br", "strong", "em", "ul", "ol", "li", "a"]
ALLOWED_ATTRS = {"a": ["href", "title"]}


def clean_html(value: str) -> str:
    """Allow-list sanitiser for rich text (notice bodies, remarks). Scripts and handlers are stripped."""
    return bleach.clean(value or "", tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, protocols=["https", "mailto"], strip=True)


def clean_text(value: str) -> str:
    """Plain text only: strip every tag."""
    return bleach.clean(value or "", tags=[], strip=True).strip()
