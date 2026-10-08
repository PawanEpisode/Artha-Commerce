import pytest

from core import plans


@pytest.fixture(autouse=True)
def _reset():
    yield
    plans.register_plan_provider(None)


def test_every_student_is_on_free_until_a_provider_is_registered():
    assert plans.plan_code_for("any-user") == "free"


def test_a_registered_provider_answers_and_can_be_removed():
    plans.register_plan_provider(lambda user_id: "pro" if user_id == "u1" else "free")
    assert plans.plan_code_for("u1") == "pro"
    assert plans.plan_code_for("u2") == "free"
    plans.register_plan_provider(None)
    assert plans.plan_code_for("u1") == "free"


def test_an_empty_answer_means_free():
    plans.register_plan_provider(lambda user_id: "")
    assert plans.plan_code_for("u1") == "free"
