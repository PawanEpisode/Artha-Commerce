"""
Content sniffing for uploads, pure functions over the first bytes of an object. A kind registers one (`KindSpec.sniff`);
`complete_upload` reads `sniff_bytes` through `Storage.read_range` and rejects the file with the returned reason before it
is ever scanned or opened. A client-declared MIME type is a claim, not evidence.
"""

from __future__ import annotations

import re

PDF_WINDOW = 1024  # the PDF spec lets a reader accept the header anywhere in the first 1,024 bytes
PDF_SNIFF_BYTES = PDF_WINDOW + 8  # room for the whole `%PDF-1.7` token of a header starting at the last allowed offset
_PDF_HEADER = re.compile(rb"%PDF-[12]\.\d")

TYPE_MISMATCH = "type_mismatch"


def pdf_header_offset(head: bytes) -> int | None:
    """Where the `%PDF-1.x` or `%PDF-2.x` header starts, or None when it does not start within the first 1 KB."""
    match = _PDF_HEADER.search(head)
    return match.start() if match and match.start() < PDF_WINDOW else None


def pdf_sniff(head: bytes) -> str | None:
    """
    None for a file that starts like a PDF, else the rejection reason `type_mismatch`. Data before the header is tolerated
    only inside the first 1 KB; a file that hides the header deeper (an archive or an image with a PDF appended, the usual
    polyglot) is refused. The full structural check is the inspect job's, with a real parser.
    """
    return None if pdf_header_offset(head) is not None else TYPE_MISMATCH
