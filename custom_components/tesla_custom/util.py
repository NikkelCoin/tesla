"""Utilities for tesla."""

from functools import partial
import logging
import ssl
from urllib.parse import urlsplit

import httpx
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import SERVER_SOFTWARE, USER_AGENT
from teslajsonpy.const import AUTH_DOMAIN

try:
    from homeassistant.util.ssl import (
        SSL_ALPN_HTTP11_HTTP2,
        create_client_context,
    )
except ImportError:
    # Home Assistant before create_client_context/ALPN constants.
    from homeassistant.util.ssl import client_context

    SSL_ALPN_HTTP11_HTTP2 = ("http/1.1", "h2")
    create_client_context = None

_LOGGER = logging.getLogger(__name__)

_AUTH_DOMAIN_CN = "https://auth.tesla.cn"
_DEFAULT_HEADERS = {USER_AGENT: SERVER_SOFTWARE}


def _create_ha_client_ssl_context() -> ssl.SSLContext:
    """Create an independent Home Assistant client SSL context."""
    if create_client_context is not None:
        try:
            return create_client_context(alpn_protocols=SSL_ALPN_HTTP11_HTTP2)
        except TypeError:
            return create_client_context()

    ssl_context = client_context()
    ssl_context.set_alpn_protocols(list(SSL_ALPN_HTTP11_HTTP2))
    return ssl_context


def create_tesla_ssl_context(
    *,
    api_proxy_cert: str | None = None,
    minimum_version: ssl.TLSVersion | None = ssl.TLSVersion.TLSv1_3,
) -> ssl.SSLContext:
    """Create a Home Assistant client SSL context for Tesla requests."""
    ssl_context = _create_ha_client_ssl_context()

    if minimum_version is not None:
        ssl_context.minimum_version = minimum_version

    if api_proxy_cert:
        try:
            ssl_context.load_verify_locations(api_proxy_cert)
            if _LOGGER.isEnabledFor(logging.DEBUG):
                _LOGGER.debug("Trusting CA from %s", api_proxy_cert)
        except (FileNotFoundError, ssl.SSLError):
            _LOGGER.warning(
                "Unable to load custom SSL certificate from %s",
                api_proxy_cert,
            )

    return ssl_context


def _normalize_mount_url(auth_domain: str | None) -> str:
    """Return the scheme and host part of an auth-domain URL."""
    if not auth_domain:
        return AUTH_DOMAIN

    if "://" not in auth_domain:
        auth_domain = f"https://{auth_domain}"

    parsed = urlsplit(auth_domain)
    if not parsed.netloc:
        return AUTH_DOMAIN

    return f"{parsed.scheme}://{parsed.netloc}"


def _auth_mount_urls(auth_domain: str | None) -> set[str]:
    """Return Tesla auth hosts that need the auth transport."""
    return {
        _normalize_mount_url(AUTH_DOMAIN),
        _normalize_mount_url(_AUTH_DOMAIN_CN),
        _normalize_mount_url(auth_domain),
    }


def _create_tesla_ssl_contexts(
    api_proxy_cert: str | None,
) -> tuple[ssl.SSLContext, ssl.SSLContext]:
    """Create the default and auth-domain SSL contexts."""
    # Keep TLS 1.3 scoped to auth hosts so local Fleet API proxies can
    # continue to negotiate their own supported TLS version.
    return (
        create_tesla_ssl_context(
            api_proxy_cert=api_proxy_cert,
            minimum_version=None,
        ),
        create_tesla_ssl_context(),
    )


def create_tesla_httpx_client(
    *,
    api_proxy_cert: str | None = None,
    auth_domain: str | None = AUTH_DOMAIN,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
    ssl_context: ssl.SSLContext | None = None,
    auth_ssl_context: ssl.SSLContext | None = None,
) -> httpx.AsyncClient:
    """Create an httpx client compatible with Tesla auth."""
    if ssl_context is None or auth_ssl_context is None:
        ssl_context, auth_ssl_context = _create_tesla_ssl_contexts(api_proxy_cert)

    mounts = {
        mount_url: httpx.AsyncHTTPTransport(
            verify=auth_ssl_context,
            http2=True,
        )
        for mount_url in _auth_mount_urls(auth_domain)
    }

    return httpx.AsyncClient(
        headers=dict(headers or _DEFAULT_HEADERS),
        timeout=timeout,
        verify=ssl_context,
        http2=True,
        mounts=mounts,
    )


async def async_create_tesla_httpx_client(
    hass: HomeAssistant,
    *,
    api_proxy_cert: str | None = None,
    auth_domain: str | None = AUTH_DOMAIN,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
) -> httpx.AsyncClient:
    """Create a Tesla httpx client without blocking the event loop."""
    ssl_context, auth_ssl_context = await hass.async_add_executor_job(
        partial(_create_tesla_ssl_contexts, api_proxy_cert)
    )
    return create_tesla_httpx_client(
        api_proxy_cert=api_proxy_cert,
        auth_domain=auth_domain,
        headers=headers,
        timeout=timeout,
        ssl_context=ssl_context,
        auth_ssl_context=auth_ssl_context,
    )


__all__ = [
    "async_create_tesla_httpx_client",
    "create_tesla_httpx_client",
    "create_tesla_ssl_context",
]
