"""One rule for the exam date: the student's own, else the start of the term they chose."""

from datetime import date

import pytest

from modules.coverage import selectors
from modules.coverage.models import Enrollment
from modules.syllabus.models import ExamTerm
from modules.syllabus.tests.helpers import make_scheme

pytestmark = pytest.mark.django_db
USER = "00000000-0000-0000-0000-0000000000a1"


def _enrol(**fields):
    scheme = make_scheme()
    return Enrollment.objects.create(user_id=USER, scheme=scheme, level=scheme.level, **fields), scheme


def test_own_date_wins_then_the_term_then_none():
    enrollment, scheme = _enrol(exam_date=date(2027, 1, 5))
    assert selectors.exam_date_of(enrollment) == date(2027, 1, 5)
    term = ExamTerm.objects.create(level=scheme.level, code="2028-05", name="May 2028", exam_start=date(2027, 5, 1))
    enrollment.target_term = term
    assert selectors.exam_date_of(enrollment) == date(2027, 1, 5)
    enrollment.exam_date = None
    assert selectors.exam_date_of(enrollment) == date(2027, 5, 1)
    enrollment.target_term = None
    assert selectors.exam_date_of(enrollment) is None


def test_course_summary_uses_the_same_rule():
    enrollment, scheme = _enrol()
    enrollment.target_term = ExamTerm.objects.create(
        level=scheme.level, code="2028-05", name="May 2028", exam_start=date(2027, 5, 1)
    )
    enrollment.save()
    summary = selectors.course_summary(USER, today=date(2027, 4, 21))
    assert summary.exam_date == date(2027, 5, 1) and summary.days_remaining == 10
