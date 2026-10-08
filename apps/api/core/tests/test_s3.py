"""SigV4 signing checked against the worked example in AWS's documentation, and the multipart calls against a fake endpoint."""

from datetime import UTC, datetime

import httpx
import pytest

from core.s3 import Part, S3Client, get_s3
from core.storage import StorageError

AWS = S3Client(
    "https://examplebucket.s3.amazonaws.com",
    "us-east-1",
    "AKIAIOSFODNN7EXAMPLE",
    "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
)


def test_the_presigned_url_matches_the_example_in_the_aws_documentation():
    url = AWS.presign(
        "GET",
        "ignored",
        "ignored",
        expires=86400,
        now=datetime(2013, 5, 24, tzinfo=UTC),
        host="examplebucket.s3.amazonaws.com",
        path="/test.txt",
    )
    assert url.endswith("X-Amz-Signature=aeeed9bbccd4d02ee5c0109b86d86835f995330da4c265957d157751f604d404")
    assert "X-Amz-Credential=AKIAIOSFODNN7EXAMPLE%2F20130524%2Fus-east-1%2Fs3%2Faws4_request" in url


def test_a_part_url_names_the_part_and_the_upload_and_expires():
    client = S3Client("https://p.storage.supabase.co/storage/v1/s3", "ap-south-1", "k", "s")
    url = client.presign_part("notes-private", "quarantine/u/a b.pdf", "UP1", 3, expires=600)
    assert url.startswith("https://p.storage.supabase.co/storage/v1/s3/notes-private/quarantine/u/a%20b.pdf?")
    assert "partNumber=3" in url and "uploadId=UP1" in url and "X-Amz-Expires=600" in url


class Fake:
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, method, url, **kw):
        self.calls.append((method, url, kw))
        status, text = self.answers.pop(0)
        return httpx.Response(status, text=text, request=httpx.Request(method, url))


@pytest.fixture
def client():
    return S3Client("https://p.storage.supabase.co/storage/v1/s3", "ap-south-1", "k", "s")


def test_starting_listing_completing_and_aborting(monkeypatch, client):
    fake = Fake(
        (200, "<InitiateMultipartUploadResult><UploadId>UP1</UploadId></InitiateMultipartUploadResult>"),
        (
            200,
            "<ListPartsResult><IsTruncated>false</IsTruncated>"
            '<Part><PartNumber>2</PartNumber><ETag>"b"</ETag><Size>8</Size></Part>'
            '<Part><PartNumber>1</PartNumber><ETag>"a"</ETag><Size>8</Size></Part></ListPartsResult>',
        ),
        (200, "<CompleteMultipartUploadResult/>"),
        (204, ""),
    )
    monkeypatch.setattr(httpx, "request", fake)
    assert client.create_multipart("b", "k.pdf", "application/pdf") == "UP1"
    assert client.list_parts("b", "k.pdf", "UP1") == [Part(1, "a", 8), Part(2, "b", 8)]
    client.complete_multipart("b", "k.pdf", "UP1", [Part(2, "b"), Part(1, "a")])
    client.abort_multipart("b", "k.pdf", "UP1")
    methods = [c[0] for c in fake.calls]
    assert methods == ["POST", "GET", "POST", "DELETE"]
    body = fake.calls[2][2]["content"].decode()
    assert body.index("<PartNumber>1") < body.index("<PartNumber>2") and '<ETag>"a"</ETag>' in body
    assert all("Authorization" in c[2]["headers"] for c in fake.calls)
    assert "secret" not in str(fake.calls)


def test_a_refusal_or_an_outage_is_a_storage_error(monkeypatch, client):
    monkeypatch.setattr(httpx, "request", Fake((403, "no")))
    with pytest.raises(StorageError):
        client.create_multipart("b", "k", "application/pdf")

    def down(*a, **k):
        raise httpx.ConnectError("x")

    monkeypatch.setattr(httpx, "request", down)
    with pytest.raises(StorageError):
        client.abort_multipart("b", "k", "u")


def test_without_credentials_there_is_no_client(settings):
    settings.NOTES_S3_ENDPOINT = ""
    assert get_s3() is None
    settings.NOTES_S3_ENDPOINT, settings.NOTES_S3_ACCESS_KEY_ID, settings.NOTES_S3_SECRET_ACCESS_KEY = (
        "https://x/s3",
        "k",
        "s",
    )
    assert get_s3() is not None
