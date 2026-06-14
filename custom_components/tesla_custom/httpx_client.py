"""HTTPX client helpers for Tesla."""

import logging
import ssl
from urllib.parse import urlsplit

from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import SERVER_SOFTWARE, USER_AGENT
import httpx

from .util import SSL_CONTEXT, TESLA_AUTH_SSL_CONTEXT

_LOGGER = logging.getLogger(__name__)

CLIENT_TIMEOUT = 60


def _auth_mount_url(auth_domain: str) -> str:
    """Return the auth origin used by httpx mount matching."""
    parsed = urlsplit(auth_domain)
    if not parsed.scheme:
        parsed = urlsplit(f"https://{auth_domain}")
    if not parsed.netloc:
        return auth_domain.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}"


def load_api_proxy_cert(api_proxy_cert: str | None) -> None:
    """Load a custom CA into the default and Tesla auth SSL contexts."""
    if not api_proxy_cert:
        return

    try:
        SSL_CONTEXT.load_verify_locations(api_proxy_cert)
        TESLA_AUTH_SSL_CONTEXT.load_verify_locations(api_proxy_cert)
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("Trusting CA: %s", SSL_CONTEXT.get_ca_certs()[-1])
    except (FileNotFoundError, ssl.SSLError):
        _LOGGER.warning(
            "Unable to load custom SSL certificate from %s",
            api_proxy_cert,
        )


async def async_load_api_proxy_cert(
    hass: HomeAssistant, api_proxy_cert: str | None
) -> None:
    """Load a custom CA without blocking the event loop."""
    if api_proxy_cert:
        await hass.async_add_executor_job(load_api_proxy_cert, api_proxy_cert)


def create_tesla_httpx_client(auth_domain: str) -> httpx.AsyncClient:
    """Create the shared httpx client used by teslajsonpy."""
    return httpx.AsyncClient(
        headers={USER_AGENT: SERVER_SOFTWARE},
        timeout=CLIENT_TIMEOUT,
        verify=SSL_CONTEXT,
        http2=True,
        mounts={
            _auth_mount_url(auth_domain): httpx.AsyncHTTPTransport(
                verify=TESLA_AUTH_SSL_CONTEXT,
                http2=True,
            )
        },
    )
