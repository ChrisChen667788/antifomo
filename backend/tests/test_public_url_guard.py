from __future__ import annotations

import http.client
import socket
import ssl
from urllib import request

import pytest

from app.services import public_url_guard


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/admin",
        "http://10.1.2.3/private",
        "http://169.254.169.254/latest/meta-data",
        "http://[::1]/admin",
        "http://[::7f00:1]/admin",
        "http://[64:ff9b::7f00:1]/admin",
        "http://[2002:7f00:1::]/admin",
        "http://[fec0::1]/admin",
        "http://localhost:8000/healthz",
        "https://user:password@example.com/private",
    ],
)
def test_validate_public_http_url_rejects_non_public_targets(url: str) -> None:
    with pytest.raises(public_url_guard.UnsafePublicUrlError):
        public_url_guard.validate_public_http_url(url)


def test_validate_public_http_url_accepts_global_ip_literal() -> None:
    assert (
        public_url_guard.validate_public_http_url("https://93.184.216.34/article")
        == "https://93.184.216.34/article"
    )


def test_validate_public_http_url_rejects_hostname_with_any_private_answer(monkeypatch) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443)),
        ],
    )

    with pytest.raises(public_url_guard.UnsafePublicUrlError):
        public_url_guard.validate_public_http_url("https://example.test/article")


def test_redirect_handler_revalidates_target_before_following() -> None:
    handler = public_url_guard.PublicOnlyRedirectHandler()
    with pytest.raises(public_url_guard.UnsafePublicUrlError):
        handler.redirect_request(None, None, 302, "Found", {}, "http://127.0.0.1/private")


class _FakeSocket:
    def __init__(self, address: str) -> None:
        self.address = address
        self.closed = False

    def getpeername(self):
        return (self.address, 443)

    def close(self) -> None:
        self.closed = True


@pytest.mark.parametrize("peer_address", ["127.0.0.1", "fec0::1", "64:ff9b::7f00:1"])
def test_connected_peer_validation_rejects_dns_rebinding_target(
    monkeypatch,
    peer_address: str,
) -> None:
    fake_socket = _FakeSocket(peer_address)

    def fake_connect(connection) -> None:
        connection.sock = fake_socket

    monkeypatch.setattr(http.client.HTTPConnection, "connect", fake_connect)
    connection = public_url_guard.PeerValidatedHTTPConnection("example.test")

    with pytest.raises(
        public_url_guard.UnsafePublicUrlError,
        match="Connected peer is private",
    ):
        connection.connect()

    assert fake_socket.closed is True


def test_connected_peer_validation_accepts_actual_global_peer(monkeypatch) -> None:
    fake_socket = _FakeSocket("93.184.216.34")

    def fake_connect(connection) -> None:
        connection.sock = fake_socket

    monkeypatch.setattr(http.client.HTTPConnection, "connect", fake_connect)
    connection = public_url_guard.PeerValidatedHTTPConnection("example.test")

    connection.connect()

    assert connection.sock is fake_socket
    assert fake_socket.closed is False


def test_https_rebinding_peer_is_rejected_before_tls_bytes(monkeypatch) -> None:
    fake_socket = _FakeSocket("127.0.0.1")

    def fake_connect(connection) -> None:
        connection.sock = fake_socket

    class _FakeContext:
        check_hostname = True
        verify_mode = ssl.CERT_REQUIRED
        wrap_called = False

        def wrap_socket(self, sock, *, server_hostname):
            self.wrap_called = True
            return sock

    context = _FakeContext()
    monkeypatch.setattr(http.client.HTTPConnection, "connect", fake_connect)
    connection = public_url_guard.PeerValidatedHTTPSConnection(
        "example.test",
        context=context,
    )

    with pytest.raises(public_url_guard.UnsafePublicUrlError):
        connection.connect()

    assert context.wrap_called is False
    assert fake_socket.closed is True


def test_open_public_url_disables_environment_proxies(monkeypatch) -> None:
    captured_handlers = []

    class _Response:
        def geturl(self) -> str:
            return "https://93.184.216.34/article"

    class _Opener:
        def open(self, req, *, timeout):
            assert req.full_url == "https://93.184.216.34/article"
            assert timeout == 7
            return _Response()

    def fake_build_opener(*handlers):
        captured_handlers.extend(handlers)
        return _Opener()

    monkeypatch.setattr(request, "build_opener", fake_build_opener)
    response = public_url_guard.open_public_url(
        request.Request("https://93.184.216.34/article"),
        timeout_seconds=7,
    )

    assert response.geturl() == "https://93.184.216.34/article"
    proxy_handler = next(
        handler for handler in captured_handlers if isinstance(handler, request.ProxyHandler)
    )
    assert proxy_handler.proxies == {}
    assert any(
        isinstance(handler, public_url_guard.PublicOnlyHTTPHandler)
        for handler in captured_handlers
    )
    assert any(
        isinstance(handler, public_url_guard.PublicOnlyHTTPSHandler)
        for handler in captured_handlers
    )
