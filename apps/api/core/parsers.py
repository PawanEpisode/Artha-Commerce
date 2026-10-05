"""Request parsers shared by modules."""

import json

from rest_framework.exceptions import ParseError
from rest_framework.parsers import BaseParser


class PlainTextJSONParser(BaseParser):
    """
    JSON sent as `text/plain`. `navigator.sendBeacon` with a string body uses that type, which browsers treat as
    CORS-safelisted (no preflight), so the request still leaves while the tab is closing.
    """

    media_type = "text/plain"

    def parse(self, stream, media_type=None, parser_context=None):
        try:
            data = json.loads(stream.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ParseError("Malformed body.") from exc
        if not isinstance(data, dict):
            raise ParseError("Malformed body.")
        return data
