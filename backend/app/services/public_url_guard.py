from __future__ import annotations

import http.client
import ipaddress
import socket
from typing import Any
from urllib import parse, request


class UnsafePublicUrlError(ValueError):
    pass


_BLOCKED_IPV6_TRANSITION_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in (
        "::/96",
        "::ffff:0:0/96",
        "64:ff9b::/96",
        "64:ff9b:1::/48",
        "100::/64",
        "2001::/23",
        "2001:db8::/32",
        "2002::/16",
        "fec0::/10",
    )
)


def _is_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    mapped = getattr(address, "ipv4_mapped", None)
    if mapped is not None:
        address = mapped
    if isinstance(address, ipaddress.IPv6Address) and any(
        address in network for network in _BLOCKED_IPV6_TRANSITION_NETWORKS
    ):
        return False
    return bool(
        address.is_global
        and not address.is_private
        and not address.is_loopback
        and not address.is_link_local
        and not address.is_multicast
        and not address.is_reserved
        and not address.is_unspecified
        and not getattr(address, "is_site_local", False)
    )


def validate_public_http_url(url: str) -> str:
    """Require an HTTP(S) destination whose current DNS answers are globally routable."""

    raw = str(url or "").strip()
    parsed = parse.urlparse(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise UnsafePublicUrlError("Only absolute HTTP(S) URLs are allowed")
    if parsed.username or parsed.password:
        raise UnsafePublicUrlError("Credentials in URLs are not allowed")
    hostname = parsed.hostname.rstrip(".").casefold()
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        raise UnsafePublicUrlError("Local network destinations are not allowed")

    try:
        literal = ipaddress.ip_address(hostname)
        addresses = {literal}
    except ValueError:
        try:
            addresses = {
                ipaddress.ip_address(row[4][0].split("%", 1)[0])
                for row in socket.getaddrinfo(
                    hostname,
                    parsed.port or (443 if parsed.scheme.lower() == "https" else 80),
                    type=socket.SOCK_STREAM,
                )
            }
        except (OSError, ValueError) as exc:
            raise UnsafePublicUrlError("URL host could not be resolved safely") from exc

    if not addresses or any(not _is_public_address(address) for address in addresses):
        raise UnsafePublicUrlError("Private, reserved, or non-global destinations are not allowed")
    return raw


class PublicOnlyRedirectHandler(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        validate_public_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _validate_connected_peer(sock: Any) -> None:
    """Reject a socket unless the address actually reached is globally routable.

    DNS validation alone leaves a resolution-to-connect race.  The connection
    classes below run this check after the socket is established and before
    urllib sends the HTTP request.
    """

    if sock is None:
        raise UnsafePublicUrlError("URL connection did not expose a peer address")
    try:
        peer = sock.getpeername()
        raw_address = peer[0] if isinstance(peer, tuple) else peer
        address = ipaddress.ip_address(str(raw_address).split("%", 1)[0])
    except (OSError, TypeError, ValueError, IndexError) as exc:
        raise UnsafePublicUrlError("URL connection peer could not be verified") from exc
    if not _is_public_address(address):
        raise UnsafePublicUrlError(
            "Connected peer is private, reserved, or non-global"
        )


class _PeerValidatedConnectionMixin:
    sock: Any

    def connect(self) -> None:
        if getattr(self, "_tunnel_host", None):
            raise UnsafePublicUrlError("Proxy tunnels are not allowed for public URL fetches")
        super().connect()  # type: ignore[misc]
        try:
            _validate_connected_peer(self.sock)
        except Exception:
            self.close()  # type: ignore[attr-defined]
            raise


class PeerValidatedHTTPConnection(
    _PeerValidatedConnectionMixin,
    http.client.HTTPConnection,
):
    pass


class PeerValidatedHTTPSConnection(http.client.HTTPSConnection):
    def connect(self) -> None:
        if self._tunnel_host:
            raise UnsafePublicUrlError("Proxy tunnels are not allowed for public URL fetches")
        http.client.HTTPConnection.connect(self)
        try:
            _validate_connected_peer(self.sock)
            self.sock = self._context.wrap_socket(
                self.sock,
                server_hostname=self.host,
            )
        except Exception:
            self.close()
            raise


class PublicOnlyHTTPHandler(request.HTTPHandler):
    def http_open(self, req):  # type: ignore[no-untyped-def]
        return self.do_open(PeerValidatedHTTPConnection, req)


class PublicOnlyHTTPSHandler(request.HTTPSHandler):
    def https_open(self, req):  # type: ignore[no-untyped-def]
        return self.do_open(
            PeerValidatedHTTPSConnection,
            req,
            context=self._context,
        )


def open_public_url(req: request.Request, *, timeout_seconds: int):
    validate_public_http_url(req.full_url)
    opener = request.build_opener(
        request.ProxyHandler({}),
        PublicOnlyRedirectHandler(),
        PublicOnlyHTTPHandler(),
        PublicOnlyHTTPSHandler(),
    )
    response = opener.open(req, timeout=timeout_seconds)
    validate_public_http_url(response.geturl())
    return response
