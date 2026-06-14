"""Test Tesla utility helpers."""

import ssl
from unittest.mock import MagicMock, patch

from homeassistant.helpers.httpx_client import SERVER_SOFTWARE, USER_AGENT
from teslajsonpy.const import AUTH_DOMAIN

from custom_components.tesla_custom.util import (
    create_tesla_httpx_client,
    create_tesla_ssl_context,
)

from .const import TEST_API_PROXY_CERT


class FakeSSLContext:
    """Minimal SSL context for helper unit tests."""

    def __init__(self) -> None:
        """Initialize fake context."""
        self.loaded_verify_locations = []
        self.minimum_version = None

    def load_verify_locations(self, cafile):
        """Record custom CA paths."""
        self.loaded_verify_locations.append(cafile)


def test_create_tesla_ssl_context_requires_tls13() -> None:
    """Tesla auth SSL contexts require TLS 1.3."""
    ssl_context = create_tesla_ssl_context()

    assert ssl_context.minimum_version == ssl.TLSVersion.TLSv1_3


def test_create_tesla_ssl_context_loads_proxy_cert() -> None:
    """Custom proxy certificates are loaded into the SSL context."""
    fake_context = FakeSSLContext()

    with patch(
        "custom_components.tesla_custom.util._create_ha_client_ssl_context",
        return_value=fake_context,
    ):
        ssl_context = create_tesla_ssl_context(api_proxy_cert=TEST_API_PROXY_CERT)

    assert ssl_context is fake_context
    assert fake_context.minimum_version == ssl.TLSVersion.TLSv1_3
    assert fake_context.loaded_verify_locations == [TEST_API_PROXY_CERT]


def test_create_tesla_httpx_client_enables_http2_for_auth_mounts() -> None:
    """Tesla httpx clients use HTTP/2 and a TLS 1.3 auth transport."""
    default_context = FakeSSLContext()
    auth_context = FakeSSLContext()
    auth_context.minimum_version = ssl.TLSVersion.TLSv1_3

    with (
        patch(
            "custom_components.tesla_custom.util.httpx.AsyncHTTPTransport",
            side_effect=lambda **kwargs: MagicMock(kwargs=kwargs),
        ) as mock_transport,
        patch("custom_components.tesla_custom.util.httpx.AsyncClient") as mock_client,
    ):
        create_tesla_httpx_client(
            auth_domain=AUTH_DOMAIN,
            ssl_context=default_context,
            auth_ssl_context=auth_context,
        )

    for transport_call in mock_transport.call_args_list:
        assert transport_call.kwargs["http2"] is True
        assert transport_call.kwargs["verify"] is auth_context
        assert transport_call.kwargs["verify"].minimum_version == ssl.TLSVersion.TLSv1_3

    client_kwargs = mock_client.call_args.kwargs
    assert client_kwargs["headers"] == {USER_AGENT: SERVER_SOFTWARE}
    assert client_kwargs["timeout"] == 60
    assert client_kwargs["verify"] is default_context
    assert client_kwargs["http2"] is True
    assert AUTH_DOMAIN in client_kwargs["mounts"]
    assert "https://auth.tesla.cn" in client_kwargs["mounts"]
