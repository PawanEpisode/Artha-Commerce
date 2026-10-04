"""Reference data: the three courses, their levels and the exam terms offered in onboarding. Idempotent."""

from django.db import migrations

COURSES = [
    {
        "code": "ca",
        "name": "Chartered Accountancy",
        "institute_name": "ICAI",
        "institute_url": "https://www.icai.org",
        "description": "Plan, practise and revise every paper of the CA Foundation, Intermediate and Final levels.",
        "levels": [("foundation", "Foundation"), ("intermediate", "Intermediate"), ("final", "Final")],
        "terms": [("2026-11", "November 2026"), ("2027-05", "May 2027"), ("2027-11", "November 2027")],
    },
    {
        "code": "cs",
        "name": "Company Secretaryship",
        "institute_name": "ICSI",
        "institute_url": "https://www.icsi.edu",
        "description": "Stay on top of company law, securities law and governance papers across Foundation, Executive and Professional.",
        "levels": [("foundation", "Foundation"), ("executive", "Executive"), ("professional", "Professional")],
        "terms": [("2026-12", "December 2026"), ("2027-06", "June 2027"), ("2027-12", "December 2027")],
    },
    {
        "code": "cma",
        "name": "Cost and Management Accountancy",
        "institute_name": "ICMAI",
        "institute_url": "https://icmai.in",
        "description": "Build mastery in costing, management accounting and strategic finance across Foundation, Intermediate and Final.",
        "levels": [("foundation", "Foundation"), ("intermediate", "Intermediate"), ("final", "Final")],
        "terms": [("2026-12", "December 2026"), ("2027-06", "June 2027"), ("2027-12", "December 2027")],
    },
]


def seed(apps, schema_editor):
    Course = apps.get_model("syllabus", "Course")
    Level = apps.get_model("syllabus", "Level")
    ExamTerm = apps.get_model("syllabus", "ExamTerm")
    for spec in COURSES:
        course, _ = Course.objects.update_or_create(
            code=spec["code"],
            defaults={
                "name": spec["name"],
                "institute_name": spec["institute_name"],
                "institute_url": spec["institute_url"],
                "description": spec["description"],
                "is_active": True,
            },
        )
        for order, (code, name) in enumerate(spec["levels"]):
            Level.objects.update_or_create(course=course, code=code, defaults={"name": name, "sort_order": order})
        # Exam dates are left empty until confirmed from the institute's official schedule.
        for code, name in spec["terms"]:
            ExamTerm.objects.update_or_create(course=course, code=code, defaults={"name": name, "is_open": True})


class Migration(migrations.Migration):
    dependencies = [("syllabus", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
