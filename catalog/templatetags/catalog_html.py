from urllib.parse import urlparse

import bleach
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ALLOWED_TAGS = [
    "p",
    "br",
    "ul",
    "ol",
    "li",
    "strong",
    "em",
    "b",
    "i",
    "a",
    "blockquote",
    "h3",
    "h4",
    "iframe",
]
ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "target", "rel"],
    "iframe": [
        "src",
        "width",
        "height",
        "title",
        "frameborder",
        "allow",
        "allowfullscreen",
        "loading",
        "referrerpolicy",
    ],
}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]
ALLOWED_IFRAME_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
    "youtu.be",
    "vk.com",
    "www.vk.com",
    "vkvideo.ru",
    "www.vkvideo.ru",
    "video.rutube.ru",
    "rutube.ru",
    "www.rutube.ru",
}


def _is_allowed_iframe_src(src: str) -> bool:
    if not src:
        return False
    src = src.strip()
    if src.startswith("//"):
        src = f"https:{src}"
    try:
        parsed = urlparse(src)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    return host in ALLOWED_IFRAME_HOSTS or host.endswith(".vkvideo.ru")


def _iframe_attr_filter(
    tag: str,
    name: str,
    value: str,
) -> bool:
    if tag == "iframe" and name == "src":
        return _is_allowed_iframe_src(value)
    return True


@register.filter(name="sanitize_product_description")
def sanitize_product_description(value):
    raw = str(value or "")
    with_breaks = raw.replace("\r\n", "\n").replace("\r", "\n").replace(
        "\n",
        "<br>\n",
    )
    cleaned = bleach.sanitizer.Cleaner(
        tags=ALLOWED_TAGS,
        attributes={
            **ALLOWED_ATTRIBUTES,
            "iframe": _iframe_attr_filter,
        },
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    ).clean(with_breaks)
    return mark_safe(cleaned)
