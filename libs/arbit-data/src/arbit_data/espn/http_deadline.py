"""Enforce one elapsed I/O budget, including HTTP headers and chunk framing.

Synchronous system DNS resolution cannot be interrupted here. Once it returns,
all address attempts, TLS, request writes and response reads share the deadline.
"""

import io
import socket
import ssl
from functools import partial
from http.client import HTTPConnection, HTTPResponse, HTTPSConnection
from time import monotonic
from typing import Any, cast
from urllib.request import HTTPSHandler, Request


def _remaining(deadline: float) -> float:
    remaining = deadline - monotonic()
    if remaining <= 0:
        raise TimeoutError("HTTP deadline exceeded")
    return remaining


def _connect(
    address: tuple[str, int],
    timeout: float,
    source_address: tuple[str, int] | None,
    *,
    deadline: float,
) -> socket.socket:
    last_error: OSError | None = None
    for family, kind, protocol, _, endpoint in socket.getaddrinfo(
        address[0], address[1], 0, socket.SOCK_STREAM
    ):
        sock = socket.socket(family, kind, protocol)
        try:
            sock.settimeout(_remaining(deadline))
            if source_address:
                sock.bind(source_address)
            sock.connect(endpoint)
            sock.settimeout(_remaining(deadline))  # TLS uses only the remaining budget.
            return sock
        except OSError as error:
            last_error = error
            sock.close()
            _remaining(deadline)
    if last_error is not None:
        raise last_error
    raise OSError("No addresses resolved")


class _DeadlineReader(io.RawIOBase):
    def __init__(self, source: io.RawIOBase, sock: socket.socket, deadline: float):
        super().__init__()
        self._source = source
        self._socket = sock
        self._deadline = deadline

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int | None:
        self._socket.settimeout(_remaining(self._deadline))
        return self._source.readinto(buffer)

    def close(self) -> None:
        try:
            self._source.close()
        finally:
            super().close()


def _response_class(deadline: float) -> type[HTTPResponse]:
    class DeadlineResponse(HTTPResponse):
        def __init__(
            self,
            sock: socket.socket,
            debuglevel: int = 0,
            method: str | None = None,
            url: str | None = None,
        ):
            super().__init__(sock, debuglevel=debuglevel, method=method, url=url)
            assert self.fp is not None
            self.fp.close()
            source = cast(io.RawIOBase, sock.makefile("rb", buffering=0))
            self.fp = io.BufferedReader(_DeadlineReader(source, sock, deadline))

    return DeadlineResponse


class _DeadlineHTTPSConnection(HTTPSConnection):
    def __init__(self, host: str, *, deadline: float, **kwargs: Any):
        super().__init__(host, **kwargs)
        self._deadline = deadline
        self._create_connection = partial(_connect, deadline=deadline)

    def send(self, data: Any) -> None:
        if self.sock is None:
            self.connect()
        assert self.sock is not None
        self.sock.settimeout(_remaining(self._deadline))
        super().send(data)


class DeadlineHTTPSHandler(HTTPSHandler):
    def __init__(self, context: ssl.SSLContext | None = None):
        super().__init__(context=context)
        self._ssl_context = context

    def _open_deadline(
        self, request: Request, connection_type: type[HTTPConnection], **kwargs: Any
    ) -> Any:
        if request.timeout is None:
            raise ValueError("HTTP deadline requires an explicit timeout")
        deadline = monotonic() + request.timeout

        def connection(host: str, **options: Any) -> HTTPConnection:
            if connection_type is HTTPSConnection:
                result: HTTPConnection = _DeadlineHTTPSConnection(
                    host, deadline=deadline, **options
                )
            else:
                result = connection_type(host, **options)
            result.response_class = _response_class(deadline)
            return result

        return self.do_open(connection, request, **kwargs)

    def https_open(self, request: Request) -> Any:
        return self._open_deadline(request, HTTPSConnection, context=self._ssl_context)
