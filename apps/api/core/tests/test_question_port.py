import uuid

import pytest

from core import question_port as port
from core.question_port import NullQuestionProvider, QuestionSource, QuestionSourceUnavailable


@pytest.fixture(autouse=True)
def _reset():
    port.register_question_provider(None)
    yield
    port.register_question_provider(None)


class Bank:
    def source_for(self, user_id, question_id, version_id):
        return QuestionSource(question_id, version_id, "Because.")


def test_nothing_registered_means_no_provider():
    assert port.get_question_provider() is None


def test_a_registered_provider_is_returned_and_the_last_one_wins():
    first, second = Bank(), Bank()
    port.register_question_provider(first)
    port.register_question_provider(second)
    assert port.get_question_provider() is second
    assert isinstance(second, port.QuestionProvider)


def test_the_null_provider_counts_as_absent_and_refuses_when_called():
    null = NullQuestionProvider()
    port.register_question_provider(null)
    assert port.get_question_provider() is None
    with pytest.raises(QuestionSourceUnavailable) as e:
        null.source_for("u", uuid.uuid4(), uuid.uuid4())
    assert e.value.status_code == 503 and e.value.default_code == "question_source_unavailable"


def test_a_source_is_immutable_and_defaults_are_empty():
    q, v = uuid.uuid4(), uuid.uuid4()
    s = QuestionSource(q, v, "x")
    assert s.reference_labels == () and s.chapter_id is None
    with pytest.raises(AttributeError):
        s.explanation_md = "y"  # type: ignore[misc]
