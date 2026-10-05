"""Exam terms per level (data step): every course-wide term is copied to each level of its course, references are
re-pointed, and the CA and CMA attempts are set to what the institutes run. Idempotent."""

from django.db import migrations
from django.db.models import ProtectedError

# (code, name, exam_start, exam_end). Dates come from the institutes' announcements as reported in the press; verify them
# against the official schedule in Django admin (Exam terms) before showing countdowns.
CA = {
    "foundation": [
        ("2027-01", "January 2027", "2027-01-03", "2027-01-09"),
        ("2027-05", "May 2027", None, None),
        ("2027-09", "September 2027", None, None),
    ],
    "intermediate": [
        ("2027-01", "January 2027", "2027-01-02", "2027-01-12"),
        ("2027-05", "May 2027", None, None),
        ("2027-09", "September 2027", None, None),
    ],
    "final": [("2027-05", "May 2027", None, None), ("2027-09", "September 2027", None, None)],
    "spom": [],
}
CMA = {
    "foundation": [
        ("2026-12", "December 2026", "2026-12-13", "2026-12-13"),
        ("2027-06", "June 2027", None, None),
        ("2027-12", "December 2027", None, None),
    ],
    "intermediate": [
        ("2026-12", "December 2026", "2026-12-10", "2026-12-17"),
        ("2027-06", "June 2027", None, None),
        ("2027-12", "December 2027", None, None),
    ],
    "final": [
        ("2026-12", "December 2026", "2026-12-10", "2026-12-17"),
        ("2027-06", "June 2027", None, None),
        ("2027-12", "December 2027", None, None),
    ],
}


def forwards(apps, schema_editor):
    Level = apps.get_model("syllabus", "Level")
    ExamTerm = apps.get_model("syllabus", "ExamTerm")
    Scheme = apps.get_model("syllabus", "Scheme")
    try:
        Enrollment = apps.get_model("coverage", "Enrollment")
    except LookupError:
        Enrollment = None

    for old in list(ExamTerm.objects.filter(level__isnull=True)):
        for level in Level.objects.filter(course_id=old.course_id):
            new, _ = ExamTerm.objects.get_or_create(
                level=level,
                code=old.code,
                defaults={
                    "course_id": old.course_id,
                    "name": old.name,
                    "exam_start": old.exam_start,
                    "exam_end": old.exam_end,
                    "is_open": old.is_open,
                },
            )
            Scheme.objects.filter(level=level, from_term=old).update(from_term=new)
            Scheme.objects.filter(level=level, to_term=old).update(to_term=new)
            if Enrollment is not None:
                Enrollment.objects.filter(level=level, target_term=old).update(target_term=new)
        try:
            old.delete()
        except ProtectedError:  # still referenced somewhere unexpected: keep it hidden instead of losing the link
            old.is_open = False
            old.save(update_fields=["is_open"])

    for course_code, spec in (("ca", CA), ("cma", CMA)):
        for level_code, terms in spec.items():
            level = Level.objects.filter(course__code=course_code, code=level_code).first()
            if not level:
                continue
            keep = set()
            for code, name, start, end in terms:
                ExamTerm.objects.update_or_create(
                    level=level,
                    code=code,
                    defaults={
                        "course_id": level.course_id,
                        "name": name,
                        "exam_start": start,
                        "exam_end": end,
                        "is_open": True,
                    },
                )
                keep.add(code)
            for stale in ExamTerm.objects.filter(level=level).exclude(code__in=keep):
                try:
                    stale.delete()
                except ProtectedError:
                    stale.is_open = False
                    stale.save(update_fields=["is_open"])


class Migration(migrations.Migration):
    dependencies = [("syllabus", "0006_examterm_level"), ("coverage", "0001_initial")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
