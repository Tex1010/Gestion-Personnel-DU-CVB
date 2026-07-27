from django import template

register = template.Library()


@register.filter
def startswith(text, prefix):
    """Check if a string starts with a given prefix."""
    if text is None:
        return False
    return str(text).startswith(prefix)
