"""Utilities for tesla."""

import ssl
from urllib.parse import urlsplit

from homeassistant.helpers.httpx_client import SERVER_SOFTWARE, USER_AGENT
import httpx
from teslajsonpy.const import AUTH_DOMAIN

try:
    # Home Assistant 2023.4.x+
    from homeassistant.util.ssl import get_default_context

    SSL_CONTEXT = get_default_context()
except ImportError:
    from homeassistant.util.ssl import client_context

    SSL_CONTEXT = client_context()


def create_tesla_auth_ssl_context() -> ssl.SSLContext:
    """Create a TLS 1.3-only SSL context for Tesla auth requests."""
    context = ssl.create_default_context()
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3
    return context


def _normalize_auth_domain(auth_domain: str | None) -> str:
    """Normalize auth domain to the per-host HTTPX mount pattern."""
    auth_domain = auth_domain or AUTH_DOMAIN
    if "://" not in auth_domain:
        auth_domain = f"https://{auth_domain}"

    parsed = urlsplit(auth_domain)
    host = parsed.hostname
    if host is None:
        parsed = urlsplit(AUTH_DOMAIN)
        host = parsed.hostname
        if host is None:
            raise ValueError("Unable to normalize Tesla auth domain")

    if ":" in host and not host.startswith("["):
        host = f"[{host}]"

    if parsed.port:
        host = f"{host}:{parsed.port}"

    return f"{parsed.scheme or 'https'}://{host}"


def create_tesla_httpx_client(
    auth_ssl_context: ssl.SSLContext | None = None,
    *,
    auth_domain: str = AUTH_DOMAIN,
    verify_context: ssl.SSLContext = SSL_CONTEXT,
) -> httpx.AsyncClient:
    """Create a Tesla HTTP client with HTTP/2 and TLS 1.3 pinned to auth."""
    if auth_ssl_context is None:
        auth_ssl_context = create_tesla_auth_ssl_context()

    return httpx.AsyncClient(
        headers={USER_AGENT: SERVER_SOFTWARE},
        timeout=60,
        verify=verify_context,
        mounts={
            _normalize_auth_domain(auth_domain): httpx.AsyncHTTPTransport(
                http2=True,
                verify=auth_ssl_context,
            ),
        },
    )
