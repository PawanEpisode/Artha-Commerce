"""
Malware scanning behind a small protocol, so `media` never learns what ClamAV is and tests never need it.

    NullScanner    scans nothing and says so (`inline = True`): `complete_upload` marks the file clean at once. Local development
                   and tests; never use it for real uploads in production.
    ClamdScanner   streams the object to a clamd daemon with the `INSTREAM` command over TCP (`CLAMD_HOST`, `CLAMD_PORT`) or a
                   unix socket (`CLAMD_SOCKET`, which wins when set). clamd must allow the largest file: `StreamMaxLength 64M`.

`get_scanner()` reads `MEDIA_SCANNER` (`null` or `clamd`). The `media.scan` job (services.run_scan_job) feeds a scanner the
object in chunks read through `Storage.read_range`, so no file is ever held in memory or written to disk.
"""

from __future__ import annotations

import socket
import struct
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Protocol

from django.conf import settings

from core.storage import Storage

CHUNK_BYTES = 4 * 1024 * 1024
CLAMD_TIMEOUT_SECONDS = 60.0


class ScannerError(Exception):
    """The scanner could not give a verdict (down, timed out, refused the stream). The job retries; the file is not rejected."""


class TooLarge(Exception):
    """The object holds more bytes than the upload declared: the quota reserved for it would be a lie."""


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    signature: str = ""  # the engine's name for what it found; for logs and metrics, never for students


class Scanner(Protocol):
    inline: bool

    def scan(self, chunks: Iterable[bytes]) -> ScanResult: ...


class NullScanner:
    inline = True

    def scan(self, chunks: Iterable[bytes]) -> ScanResult:
        for _ in chunks:  # still drains the iterator, so size checks in `object_chunks` run in tests too
            pass
        return ScanResult(clean=True)


class ClamdScanner:
    inline = False

    def __init__(self, host: str = "", port: int = 3310, socket_path: str = "", timeout: float = CLAMD_TIMEOUT_SECONDS):
        if not (socket_path or host):
            raise ScannerError("Set CLAMD_SOCKET, or CLAMD_HOST and CLAMD_PORT.")
        self.host, self.port, self.socket_path, self.timeout = host, port, socket_path, timeout

    def _connect(self) -> socket.socket:
        try:
            if self.socket_path:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                sock.connect(self.socket_path)
            else:
                sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            return sock
        except OSError as exc:
            raise ScannerError(f"clamd unreachable: {type(exc).__name__}") from exc

    def scan(self, chunks: Iterable[bytes]) -> ScanResult:
        sock = self._connect()
        try:
            sock.sendall(b"zINSTREAM\0")
            for chunk in chunks:
                if chunk:  # a zero length would end the stream early
                    sock.sendall(struct.pack("!I", len(chunk)) + chunk)
            sock.sendall(struct.pack("!I", 0))
            reply = self._read_reply(sock)
        except OSError as exc:  # includes timeouts and a daemon that closes on a too-long stream
            raise ScannerError(f"clamd stream failed: {type(exc).__name__}") from exc
        finally:
            sock.close()
        return parse_reply(reply)

    @staticmethod
    def _read_reply(sock: socket.socket) -> bytes:
        data = b""
        while not data.endswith(b"\0") and not data.endswith(b"\n"):
            part = sock.recv(4096)
            if not part:
                break
            data += part
        return data


def parse_reply(reply: bytes) -> ScanResult:
    """`stream: OK`, `stream: <signature> FOUND` or `... ERROR` (for example when the stream is over `StreamMaxLength`)."""
    text = reply.rstrip(b"\0\n").decode("ascii", "replace").strip()
    if text.endswith("OK"):
        return ScanResult(clean=True)
    if text.endswith("FOUND"):
        signature = text.removeprefix("stream:").removesuffix("FOUND").strip()
        return ScanResult(clean=False, signature=signature[:100])
    raise ScannerError(f"clamd answered: {text[:100] or 'nothing'}")


def get_scanner() -> Scanner:
    kind = getattr(settings, "MEDIA_SCANNER", "null")
    if kind == "clamd":
        return ClamdScanner(settings.CLAMD_HOST, int(settings.CLAMD_PORT), settings.CLAMD_SOCKET)
    return NullScanner()


def object_chunks(
    storage: Storage, bucket: str, path: str, *, limit: int, chunk_bytes: int = CHUNK_BYTES
) -> Iterator[bytes]:
    """The object in `chunk_bytes` pieces through range reads. Raises `TooLarge` as soon as more than `limit` bytes exist."""
    start = 0
    while True:
        piece = storage.read_range(bucket, path, start, start + chunk_bytes - 1)
        if not piece:
            return
        start += len(piece)
        if start > limit:
            raise TooLarge
        yield piece
        if len(piece) < chunk_bytes:
            return
