import pytest
from rest_framework import status

from core.recall_port import NullRecallProvider, RecallUnavailable


def test_recall_unavailable_is_a_coded_503():
    assert RecallUnavailable.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert RecallUnavailable.default_code == "recall_unavailable"
    with pytest.raises(RecallUnavailable):
        NullRecallProvider().create_card_from_source("u", kind="fact")
