"""Exercise the actual HTTP stack through a loopback test server."""

import socket
import threading
import time
from contextlib import contextmanager
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener

from arbit_data.espn import transport as module
from arbit_data.espn.transport import EspnTransport


@contextmanager
def server(
    monkeypatch,
    *,
    body=b'{"points":0.1}',
    status=200,
    headers=None,
    delay=0,
    raw_chunks=None,
    real_clock=False,
):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append((self.path, self.headers))
            if raw_chunks is not None:
                try:
                    for chunk in raw_chunks:
                        self.wfile.write(chunk)
                        self.wfile.flush()
                        time.sleep(delay)
                except (BrokenPipeError, ConnectionResetError):
                    pass
                return
            time.sleep(delay)
            self.send_response(status)
            if "Content-Type" not in (headers or {}):
                self.send_header("Content-Type", "application/json")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def log_message(self, *args):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()

    class Loopback(module.DeadlineHTTPSHandler):
        def https_open(self, req):
            original = urlsplit(req.full_url)
            local = Request(
                f"http://127.0.0.1:{httpd.server_port}{original.path}?{original.query}",
                headers=dict(req.header_items()),
            )
            local.timeout = req.timeout
            return self._open_deadline(local, HTTPConnection)

    client = EspnTransport()
    # Replace only the network destination; keep request validation, pacing,
    # urllib error processing, redirect denial, size limits and JSON parsing real.
    client._opener = build_opener(ProxyHandler({}), module._NoRedirect(), Loopback())
    real_connect = socket.create_connection

    def local_only(address, *args, **kwargs):
        assert address[0] == "127.0.0.1", "Tests must never contact ESPN"
        return real_connect(address, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", local_only)
    real_resolve = socket.getaddrinfo

    def local_dns(host, *args, **kwargs):
        assert host == "127.0.0.1", "Tests must never resolve an external host"
        return real_resolve(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", local_dns)
    ticks = [0.0]
    if not real_clock:
        monkeypatch.setattr(module, "monotonic", lambda: ticks[0])
    monkeypatch.setattr(module, "sleep", lambda seconds: ticks.__setitem__(0, ticks[0] + seconds))
    try:
        yield client, received, ticks
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()
