"""Tests for Tesla utility helpers."""

import asyncio
import ssl
from unittest.mock import MagicMock, patch

import httpx
from teslajsonpy.const import API_URL, AUTH_DOMAIN

from custom_components.tesla_custom import util


def test_create_tesla_auth_ssl_context_requires_tls13() -> None:
    """Tesla auth SSL context uses certificate verification and TLS 1.3."""
    context = util.create_tesla_auth_ssl_context()

    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert context.minimum_version == ssl.TLSVersion.TLSv1_3
    assert context.maximum_version == ssl.TLSVersion.TLSv1_3


def test_create_tesla_httpx_client_mounts_auth_transport_only() -> None:
    """Tesla auth gets the TLS 1.3 transport; Owner API uses the default."""
    auth_domain = "https://auth.example.com:8443/oauth2/v3/token?state=test"
    auth_ssl_context = MagicMock(spec=ssl.SSLContext)
    auth_transport = MagicMock()

    with (
        patch.object(
            util.httpx, "AsyncHTTPTransport", return_value=auth_transport
        ) as transport_cls,
        patch.object(util.httpx, "AsyncClient") as client_cls,
    ):
        client = util.create_tesla_httpx_client(
            auth_ssl_context,
            auth_domain=auth_domain,
        )

    assert client is client_cls.return_value
    transport_cls.assert_called_once_with(http2=True, verify=auth_ssl_context)

    client_cls.assert_called_once()
    kwargs = client_cls.call_args.kwargs
    assert kwargs["headers"] == {util.USER_AGENT: util.SERVER_SOFTWARE}
    assert kwargs["timeout"] == 60
    assert kwargs["verify"] is util.SSL_CONTEXT
    assert kwargs["mounts"] == {"https://auth.example.com:8443": auth_transport}
    assert API_URL not in kwargs["mounts"]


def test_create_tesla_httpx_client_uses_default_auth_context() -> None:
    """Tesla HTTP client creates a TLS 1.3 context when none is provided."""
    auth_ssl_context = MagicMock(spec=ssl.SSLContext)
    auth_transport = MagicMock()

    with (
        patch.object(
            util, "create_tesla_auth_ssl_context", return_value=auth_ssl_context
        ) as context_factory,
        patch.object(util.httpx, "AsyncHTTPTransport", return_value=auth_transport),
        patch.object(util.httpx, "AsyncClient") as client_cls,
    ):
        util.create_tesla_httpx_client()

    context_factory.assert_called_once_with()
    assert client_cls.call_args.kwargs["mounts"] == {AUTH_DOMAIN: auth_transport}


def test_create_tesla_httpx_client_routes_only_auth_host_to_auth_transport() -> None:
    """HTTPX route selection keeps non-auth hosts on the default transport."""
    client = util.create_tesla_httpx_client(
        auth_domain=f"{AUTH_DOMAIN}/oauth2/v3/token?state=test",
    )

    try:
        auth_transport = client._transport_for_url(
            httpx.URL(f"{AUTH_DOMAIN}/oauth2/v3/token")
        )

        assert client._transport_for_url(httpx.URL(API_URL)) is not auth_transport
        assert (
            client._transport_for_url(
                httpx.URL("https://fleet-api.prd.na.vn.cloud.tesla.com")
            )
            is not auth_transport
        )
    finally:
        asyncio.run(client.aclose())
