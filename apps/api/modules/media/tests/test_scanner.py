"""The clamd client against a fake clamd that speaks the INSTREAM protocol over TCP and over a unix socket."""

import os
import socket
import socketserver
import struct
import tempfile
import threading

import pytest

from modules.media import scanner
from modules.media.scanner import ClamdScanner, NullScanner, ScannerError, ScanResult

EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


class FakeClamd(socketserver.StreamRequestHandler):
    """Reads `zINSTREAM\\0`, length-prefixed chunks and a zero chunk, then answers like clamd (z-commands answer with NUL)."""

    frames: list[int] = []

    def handle(self):
        command = b""
        while not command.endswith(b"\0"):
            command += self.rfile.read(1)
        assert command == b"zINSTREAM\0"
        data, sizes = b"", []
        while True:
            (length,) = struct.unpack("!I", self.rfile.read(4))
            if length == 0:
                break
            sizes.append(length)
            data += self.rfile.read(length)
        type(self).frames = sizes
        if b"BREAK-THE-STREAM" in data:
            self.wfile.write(b"INSTREAM size limit exceeded. ERROR\0")
        elif EICAR in data:
            self.wfile.write(b"stream: Win.Test.EICAR_HDB-1 FOUND\0")
        else:
            self.wfile.write(b"stream: OK\0")


@pytest.fixture
def tcp_server():
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), FakeClamd)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address
    server.shutdown()
    server.server_close()


@pytest.fixture
def unix_server():
    path = os.path.join(tempfile.mkdtemp(), "clamd.sock")
    server = socketserver.ThreadingUnixStreamServer(path, FakeClamd)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield path
    server.shutdown()
    server.server_close()


def test_a_clean_stream_over_tcp_is_ok_and_chunks_are_framed(tcp_server):
    host, port = tcp_server
    result = ClamdScanner(host=host, port=port).scan(iter([b"a" * 1000, b"", b"b" * 24]))
    assert result == ScanResult(clean=True) and FakeClamd.frames == [
        1000,
        24,
    ]  # an empty chunk is never sent as the terminator


def test_a_known_signature_is_found_over_a_unix_socket(unix_server):
    result = ClamdScanner(socket_path=unix_server).scan([b"harmless ", EICAR])
    assert result.clean is False and result.signature == "Win.Test.EICAR_HDB-1"


def test_the_socket_wins_over_host_and_port(unix_server):
    assert ClamdScanner(host="203.0.113.1", port=1, socket_path=unix_server).scan([b"ok"]).clean is True


def test_a_daemon_error_is_a_scanner_error_not_a_verdict(tcp_server):
    host, port = tcp_server
    with pytest.raises(ScannerError, match="size limit"):
        ClamdScanner(host=host, port=port).scan([b"BREAK-THE-STREAM"])


def test_an_unreachable_daemon_is_a_scanner_error():
    with socket.socket() as probe:  # a port nobody listens on
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with pytest.raises(ScannerError, match="unreachable"):
        ClamdScanner(host="127.0.0.1", port=port, timeout=1).scan([b"x"])
    with pytest.raises(ScannerError, match="unreachable"):
        ClamdScanner(socket_path="/nonexistent/clamd.sock").scan([b"x"])


def test_a_scanner_needs_an_address():
    with pytest.raises(ScannerError):
        ClamdScanner()


def test_replies_are_parsed():
    assert scanner.parse_reply(b"stream: OK\0").clean is True
    assert scanner.parse_reply(b"stream: Eicar-Signature FOUND\n") == ScanResult(False, "Eicar-Signature")
    for bad in (b"", b"stream: lstat() failed. ERROR\0", b"garbage"):
        with pytest.raises(ScannerError):
            scanner.parse_reply(bad)


def test_the_null_scanner_is_inline_and_drains_the_stream():
    drained = []
    assert NullScanner.inline is True and ClamdScanner.inline is False
    assert NullScanner().scan(drained.append(c) or c for c in [b"a", b"b"]).clean is True
    assert drained == [b"a", b"b"]


def test_get_scanner_follows_the_setting(settings):
    settings.MEDIA_SCANNER = "null"
    assert isinstance(scanner.get_scanner(), NullScanner)
    settings.MEDIA_SCANNER, settings.CLAMD_HOST, settings.CLAMD_PORT, settings.CLAMD_SOCKET = "clamd", "clam", 3311, ""
    got = scanner.get_scanner()
    assert isinstance(got, ClamdScanner) and (got.host, got.port, got.socket_path) == ("clam", 3311, "")
    settings.MEDIA_SCANNER, settings.CLAMD_SOCKET = "clamd", "/run/clamd.sock"
    assert scanner.get_scanner().socket_path == "/run/clamd.sock"


class Store:
    def __init__(self, data):
        self.data, self.calls = data, []

    def read_range(self, bucket, path, start, end):
        self.calls.append((start, end))
        return self.data[start : end + 1]


def test_object_chunks_reads_in_ranges_and_stops_at_the_end():
    store = Store(b"0123456789")
    assert list(scanner.object_chunks(store, "b", "p", limit=100, chunk_bytes=4)) == [b"0123", b"4567", b"89"]
    assert store.calls == [(0, 3), (4, 7), (8, 11)]
    assert list(scanner.object_chunks(Store(b"01234567"), "b", "p", limit=100, chunk_bytes=4)) == [b"0123", b"4567"]
    assert list(scanner.object_chunks(Store(b""), "b", "p", limit=100)) == []


def test_object_chunks_refuses_more_than_the_limit():
    with pytest.raises(scanner.TooLarge):
        list(scanner.object_chunks(Store(b"0123456789"), "b", "p", limit=9, chunk_bytes=4))
    assert len(list(scanner.object_chunks(Store(b"0123456789"), "b", "p", limit=10, chunk_bytes=4))) == 3
