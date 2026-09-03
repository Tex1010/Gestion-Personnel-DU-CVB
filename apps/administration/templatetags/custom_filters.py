from django import template

register = template.Library()

SENSITIVE_PATTERNS = [
    # password=secret123, passwd=secret123, pwd=secret123
    (r"(password|passwd|pwd)\s*=\s*[^\s&]+", r"\1=***"),
    # token=abc456
    (r"(token|access_token|refresh_token|api_key|apikey|key)\s*=\s*[^\s&]+", r"\1=***"),
    # cookie=sessionid=xyz or Set-Cookie: sessionid=xyz
    (r"(sessionid|cookie|auth)\s*=\s*[^\s&;]+", r"\1=***"),
    # Authorization: Bearer abc123
    (r"Authorization:\s*Bearer\s+[^\s]+", "Authorization: Bearer ***"),
    # Generic secret=value (catch-all for common patterns)
    (r"(secret|credential)\s*=\s*[^\s&]+", r"\1=***"),
]


@register.filter
def startswith(text, prefix):
    """Check if a string starts with a given prefix."""
    if text is None:
        return False
    return str(text).startswith(prefix)


@register.filter
def mask_sensitive(text):
    """Mask sensitive values like passwords, tokens, and cookies in log messages."""
    if not text:
        return text
    import re
    masked = str(text)
    for pattern, replacement in SENSITIVE_PATTERNS:
        masked = re.sub(pattern, replacement, masked, flags=re.IGNORECASE)
    return masked
