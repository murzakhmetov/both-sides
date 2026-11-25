"""Security headers, Host and Origin checks."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

#: No inline script or style anywhere; the demo page may frame this app's own pages.
CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'none'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "media-src 'self'",
        "connect-src 'self'",
        "frame-src 'self'",
        "frame-ancestors 'self'",
        "base-uri 'none'",
        "form-action 'self'",
    )
)

SECURITY_HEADERS = (
    ("Content-Security-Policy", CONTENT_SECURITY_POLICY),
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "SAMEORIGIN"),
    ("Referrer-Policy", "no-referrer"),
    ("Cross-Origin-Resource-Policy", "same-origin"),
    ("Permissions-Policy", "camera=(), geolocation=(), microphone=()"),
    ("Cache-Control", "no-store"),
)


def _hostname(host_header: str) -> str | None:
    try:
        parts = urlsplit(f"//{host_header}")
        _ = parts.port  # raises ValueError for a broken port
    except ValueError:
        return None
    if parts.username or parts.password or parts.path or parts.query:
        return None
    return parts.hostname


def host_allowed(host_header: str, extra: frozenset[str] = frozenset()) -> bool:
    """Allow this machine and private addresses, so DNS rebinding gets nowhere."""
    name = _hostname(host_header)
    if not name:
        return False
    if name == "localhost" or name in extra:
        return True
    try:
        address = ipaddress.ip_address(name)
    except ValueError:
        return False
    return address.is_loopback or address.is_private


def origin_allowed(origin: str, host_header: str) -> bool:
    """True when the page that sent the request came from this server."""
    try:
        parts = urlsplit(origin)
    except ValueError:
        return False
    return parts.scheme in {"http", "https"} and parts.netloc != "" and parts.netloc == host_header
