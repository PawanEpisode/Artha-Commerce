"""
A small S3 client for multipart uploads (Supabase Storage speaks the S3 protocol): SigV4 signing with the standard library,
no boto3 (it would weigh down the Vercel bundle). Server side only. Used by notes' resumable upload: the API starts, lists,
completes and aborts a multipart upload and signs one short-lived URL per part, so the browser can send parts straight to storage
and resend only the ones that failed.

[VERIFY] Written to the S3 specification and tested against AWS's published signing example; it still needs one real upload
against the project's Supabase S3 endpoint (`docs/F-03-ROLLOUT.md` says how) before the feature is switched on.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import quote
from xml.etree import ElementTree

import httpx
from django.conf import settings

from .storage import StorageError

TIMEOUT = httpx.Timeout(15.0, connect=3.0)
ALGORITHM = "AWS4-HMAC-SHA256"
UNSIGNED = "UNSIGNED-PAYLOAD"
_NS = re.compile(r"\{[^}]*\}")


def _quote(value: str, safe: str = "-_.~") -> str:
    return quote(value, safe=safe)


def _hmac(key: bytes, message: str) -> bytes:
    return hmac.new(key, message.encode(), hashlib.sha256).digest()


def _signing_key(secret: str, day: str, region: str) -> bytes:
    return _hmac(_hmac(_hmac(_hmac(("AWS4" + secret).encode(), day), region), "s3"), "aws4_request")


@dataclass(frozen=True)
class Part:
    number: int
    etag: str
    size: int = 0


class S3Client:
    def __init__(self, endpoint: str, region: str, key_id: str, secret: str):
        self.endpoint, self.region, self.key_id, self.secret = endpoint.rstrip("/"), region, key_id, secret
        self.host = re.sub(r"^https?://", "", self.endpoint).split("/")[0]

    # --- Signing ---------------------------------------------------------------------------------------------------------
    def _path(self, bucket: str, key: str) -> str:
        base = "/" + self.endpoint.split("/", 3)[3] if self.endpoint.count("/") >= 3 else ""
        return f"{base}/{_quote(bucket)}/{_quote(key, safe='/-_.~')}"

    def _canonical_query(self, query: dict[str, str]) -> str:
        return "&".join(f"{_quote(k)}={_quote(str(v))}" for k, v in sorted(query.items()))

    def presign(
        self,
        method: str,
        bucket: str,
        key: str,
        query: dict[str, str] | None = None,
        *,
        expires: int = 900,
        now: datetime | None = None,
        host: str | None = None,
        path: str | None = None,
    ) -> str:
        """A URL that lets whoever holds it make this one request for `expires` seconds (query-string SigV4)."""
        now = now or datetime.now(UTC)
        stamp, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
        host = host or self.host
        path = path or self._path(bucket, key)
        scope = f"{day}/{self.region}/s3/aws4_request"
        params = {
            **(query or {}),
            "X-Amz-Algorithm": ALGORITHM,
            "X-Amz-Credential": f"{self.key_id}/{scope}",
            "X-Amz-Date": stamp,
            "X-Amz-Expires": str(expires),
            "X-Amz-SignedHeaders": "host",
        }
        canonical_query = self._canonical_query(params)
        canonical = "\n".join([method, path, canonical_query, f"host:{host}\n", "host", UNSIGNED])
        to_sign = "\n".join([ALGORITHM, stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()])
        signature = hmac.new(_signing_key(self.secret, day, self.region), to_sign.encode(), hashlib.sha256).hexdigest()
        scheme = self.endpoint.split("://", 1)[0] if "://" in self.endpoint else "https"
        return f"{scheme}://{host}{path}?{canonical_query}&X-Amz-Signature={signature}"

    def presign_part(self, bucket: str, key: str, upload_id: str, number: int, *, expires: int = 3600) -> str:
        return self.presign("PUT", bucket, key, {"partNumber": str(number), "uploadId": upload_id}, expires=expires)

    # --- Calls the API makes itself --------------------------------------------------------------------------------------
    def _headers(self, method: str, path: str, query: dict[str, str], body: bytes, now: datetime) -> dict[str, str]:
        stamp, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
        payload = hashlib.sha256(body).hexdigest()
        signed = {"host": self.host, "x-amz-content-sha256": payload, "x-amz-date": stamp}
        names = ";".join(signed)
        canonical = "\n".join(
            [
                method,
                path,
                self._canonical_query(query),
                "".join(f"{k}:{v}\n" for k, v in signed.items()),
                names,
                payload,
            ]
        )
        scope = f"{day}/{self.region}/s3/aws4_request"
        to_sign = "\n".join([ALGORITHM, stamp, scope, hashlib.sha256(canonical.encode()).hexdigest()])
        signature = hmac.new(_signing_key(self.secret, day, self.region), to_sign.encode(), hashlib.sha256).hexdigest()
        auth = f"{ALGORITHM} Credential={self.key_id}/{scope}, SignedHeaders={names}, Signature={signature}"
        return {"x-amz-content-sha256": payload, "x-amz-date": stamp, "Authorization": auth}

    def _call(self, method: str, bucket: str, key: str, query: dict[str, str], body: bytes = b"") -> httpx.Response:
        path = self._path(bucket, key)
        headers = self._headers(method, path, query, body, datetime.now(UTC))
        url = f"{self.endpoint.split('/', 3)[0]}//{self.host}{path}"
        if query:
            url += "?" + self._canonical_query(query)
        try:
            response = httpx.request(method, url, headers=headers, content=body or None, timeout=TIMEOUT)
        except httpx.HTTPError as exc:
            raise StorageError(f"Storage unreachable: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            raise StorageError(f"Storage answered {response.status_code}")
        return response

    def create_multipart(self, bucket: str, key: str, content_type: str) -> str:
        response = self._call("POST", bucket, key, {"uploads": ""})
        found = _tag(response.text, "UploadId")
        if not found:
            raise StorageError("Storage gave no upload id.")
        return found

    def list_parts(self, bucket: str, key: str, upload_id: str) -> list[Part]:
        parts: list[Part] = []
        marker = "0"
        while True:
            root = ElementTree.fromstring(
                self._call("GET", bucket, key, {"uploadId": upload_id, "part-number-marker": marker}).text
            )
            for node in root.iter():
                if _NS.sub("", node.tag) == "Part":
                    fields = {_NS.sub("", c.tag): (c.text or "") for c in node}
                    parts.append(Part(int(fields["PartNumber"]), fields["ETag"].strip('"'), int(fields.get("Size", 0))))
            truncated = _tag(ElementTree.tostring(root, encoding="unicode"), "IsTruncated") == "true"
            next_marker = _tag(ElementTree.tostring(root, encoding="unicode"), "NextPartNumberMarker")
            if not truncated or not next_marker:
                return sorted(parts, key=lambda p: p.number)
            marker = next_marker

    def complete_multipart(self, bucket: str, key: str, upload_id: str, parts: list[Part]) -> None:
        body = (
            "<CompleteMultipartUpload>"
            + "".join(
                f'<Part><PartNumber>{p.number}</PartNumber><ETag>"{p.etag.strip(chr(34))}"</ETag></Part>'
                for p in sorted(parts, key=lambda p: p.number)
            )
            + "</CompleteMultipartUpload>"
        )
        self._call("POST", bucket, key, {"uploadId": upload_id}, body.encode())

    def abort_multipart(self, bucket: str, key: str, upload_id: str) -> None:
        self._call("DELETE", bucket, key, {"uploadId": upload_id})


def _tag(xml: str, name: str) -> str | None:
    match = re.search(rf"<(?:\w+:)?{name}>([^<]*)</(?:\w+:)?{name}>", xml)
    return match.group(1) if match else None


def get_s3() -> S3Client | None:
    """None when this deployment has no S3 credentials: resumable upload then stays off and every upload is one PUT."""
    if not (settings.NOTES_S3_ENDPOINT and settings.NOTES_S3_ACCESS_KEY_ID and settings.NOTES_S3_SECRET_ACCESS_KEY):
        return None
    return S3Client(
        settings.NOTES_S3_ENDPOINT,
        settings.NOTES_S3_REGION or "us-east-1",
        settings.NOTES_S3_ACCESS_KEY_ID,
        settings.NOTES_S3_SECRET_ACCESS_KEY,
    )
