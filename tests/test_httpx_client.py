"""Tests for Tesla HTTPX client helpers."""

import ssl
from unittest.mock import MagicMock, patch

from custom_components.tesla_custom import httpx_client
from custom_components.tesla_custom.util import TESLA_AUTH_SSL_CONTEXT


def test_create_tesla_httpx_client_enables_http2_for_client_and_auth_mount() -> None:
    """Client and auth transport are created with HTTP/2 support."""
    auth_transport = MagicMock()

    with (
        patch.object(
            httpx_client.httpx, "AsyncHTTPTransport", return_value=auth_transport
        ) as mock_transport,
        patch.object(httpx_client.httpx, "AsyncClient") as mock_client,
    ):
        httpx_client.create_tesla_httpx_client("https://auth.tesla.com")

    mock_transport.assert_called_once_with(
        verify=httpx_client.TESLA_AUTH_SSL_CONTEXT,
        http2=True,
    )
    mock_client.assert_called_once_with(
        headers={httpx_client.USER_AGENT: httpx_client.SERVER_SOFTWARE},
        timeout=httpx_client.CLIENT_TIMEOUT,
        verify=httpx_client.SSL_CONTEXT,
        http2=True,
        mounts={"https://auth.tesla.com": auth_transport},
    )


def test_auth_ssl_context_requires_tls13() -> None:
    """Tesla Auth uses a TLS 1.3-only SSL context."""
    assert TESLA_AUTH_SSL_CONTEXT.minimum_version is ssl.TLSVersion.TLSv1_3
    assert TESLA_AUTH_SSL_CONTEXT.maximum_version is ssl.TLSVersion.TLSv1_3


def test_load_api_proxy_cert_loads_default_and_auth_contexts() -> None:
    """Custom CA loading still covers API/proxy and auth transports."""
    default_context = MagicMock()
    auth_context = MagicMock()

    with (
        patch.object(httpx_client, "SSL_CONTEXT", default_context),
        patch.object(httpx_client, "TESLA_AUTH_SSL_CONTEXT", auth_context),
    ):
        httpx_client.load_api_proxy_cert("/path/to/certificate.pem")

    default_context.load_verify_locations.assert_called_once_with(
        "/path/to/certificate.pem"
    )
    auth_context.load_verify_locations.assert_called_once_with(
        "/path/to/certificate.pem"
    )
