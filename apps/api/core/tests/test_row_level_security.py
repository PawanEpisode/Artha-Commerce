"""
Row Level Security is our second wall: Django is the only writer, so the Supabase Data API (PostgREST) must be able
to read nothing. `core.apps.enable_rls_everywhere` switches RLS on for every public table after each migrate. These
tests pin that for every syllabus, coverage, tracking and focus table, including ones added later (tables come from the models).
"""

import pytest
from django.apps import apps
from django.db import connection
from django.db.models.signals import post_migrate

APP_LABELS = (
    "syllabus",
    "coverage",
    "tracking",
    "focus",
    "profiles",
    "notifications",
    "core",
    "media",
    "notes",
    "today",
    "questionbank",
    "practice",
    "pyq",
    "mcqbank",
    "analytics",
    "paperanalysis",
    "progression",
    "amendments",
    "mocktest",
    "material",
)


def app_tables(*labels: str) -> list[str]:
    return sorted(
        {
            model._meta.db_table
            for label in labels
            for model in apps.get_app_config(label).get_models(include_auto_created=True)
        }
    )


TABLES = app_tables(*APP_LABELS)


def test_the_tables_under_test_are_the_ones_we_think():
    # Guards the test itself: if model discovery ever returned nothing, the Postgres checks below would pass vacuously.
    assert {"syllabus_scheme", "syllabus_chapter", "syllabus_chaptermap", "syllabus_report"} <= set(TABLES)
    assert {"coverage_enrollment", "coverage_event", "coverage_chapterprogress", "coverage_rollup"} <= set(TABLES)
    assert {
        "tracking_studysession",
        "tracking_activestopwatch",
        "tracking_trackersettings",
        "tracking_goal",
        "tracking_dailyrollup",
        "tracking_hourbucket",
        "tracking_sessionaudit",
    } <= set(TABLES)
    assert {"focus_activetimer", "focus_focussettings"} <= set(TABLES)


def test_the_notes_media_and_core_tables_are_covered():
    assert {"core_job", "media_attachment"} <= set(TABLES)
    assert {
        "notes_quotaplan",
        "notes_quotausage",
        "notes_note",
        "notes_noteversion",
        "notes_tag",
        "notes_itemtag",
        "notes_noteimage",
        "notes_settings",
        "notes_monthlyusage",
        "notes_document",
        "notes_filecontent",
        "notes_filepage",
        "notes_documentchapter",
        "notes_annotation",
        "notes_exportjob",
    } <= set(TABLES)


def test_the_notification_tables_are_covered():
    assert {
        "notifications_settings",
        "notifications_preference",
        "notifications_device",
        "notifications_notification",
        "notifications_delivery",
        "notifications_scheduledjob",
        "notifications_actiontoken",
    } <= set(TABLES)


def test_the_today_tables_are_covered():
    assert {
        "today_dayplan",
        "today_task",
        "today_taskevidence",
        "today_settings",
        "today_providerconfig",
        "today_studyplan",
        "today_milestone",
        "today_replanevent",
        "today_dayfeedback",
    } <= set(TABLES)


def test_the_questionbank_tables_are_covered():
    assert {
        "questionbank_question",
        "questionbank_questionversion",
        "questionbank_option",
        "questionbank_answerkey",
        "questionbank_rubric",
        "questionbank_rubricstep",
        "questionbank_questiontopic",
        "questionbank_tag",
        "questionbank_questiontag",
        "questionbank_versionmedia",
        "questionbank_fingerprint",
        "questionbank_duplicatelink",
        "questionbank_review",
        "questionbank_report",
        "questionbank_verification",
        "questionbank_takedown",
        "questionbank_takedownitem",
        "questionbank_contributor",
        "questionbank_quotaplan",
        "questionbank_auditlog",
        "questionbank_collection",
        "questionbank_collectionitem",
        "questionbank_savedfilter",
        "questionbank_sharelink",
        "questionbank_importjob",
        "questionbank_importrow",
        "questionbank_exportjob",
        "questionbank_questionstats",
    } <= set(TABLES)


def test_the_practice_tables_are_covered():
    assert {
        "practice_session",
        "practice_attemptanswer",
        "practice_submission",
        "practice_submissionpage",
        "practice_scoringrule",
        "practice_questionstate",
        "practice_dailyrollup",
        "practice_regradejob",
        "practice_settings",
    } <= set(TABLES)


def test_the_pyq_tables_are_covered():
    assert {
        "pyq_paper",
        "pyq_choicegroup",
        "pyq_paperquestion",
        "pyq_paperlink",
        "pyq_askedcache",
        "pyq_dailyset",
        "pyq_dailysetitem",
    } <= set(TABLES)


def test_the_mcqbank_tables_are_covered():
    assert {
        "mcqbank_set",
        "mcqbank_patternprofile",
        "mcqbank_testpreset",
        "mcqbank_externallog",
        "mcqbank_refsource",
        "mcqbank_adaptiverun",
        "mcqbank_adaptiveround",
        "mcqbank_abilityestimate",
    } <= set(TABLES)


def test_the_amendments_tables_are_covered():
    assert {
        "amendments_amendment",
        "amendments_revision",
        "amendments_revisionsubject",
        "amendments_revisionterm",
        "amendments_change",
        "amendments_changeversion",
        "amendments_changemap",
        "amendments_cardstate",
        "amendments_auditlog",
    } <= set(TABLES)


def test_rls_is_switched_on_after_every_migrate():
    assert any(receiver[0][0] == "core.enable_rls_everywhere" for receiver in post_migrate.receivers)


@pytest.mark.django_db
@pytest.mark.skipif(
    connection.vendor != "postgresql", reason="Row Level Security only exists on PostgreSQL (CI runs it)"
)
def test_row_level_security_is_enabled_on_every_syllabus_and_coverage_table():
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.relname, c.relrowsecurity
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND c.relname = ANY(%s)
            """,
            [TABLES],
        )
        found = dict(cursor.fetchall())
    assert not [t for t in TABLES if t not in found], "tables missing from the database"
    assert [t for t, enabled in found.items() if not enabled] == [], "RLS is off on these tables"


@pytest.mark.django_db
@pytest.mark.skipif(
    connection.vendor != "postgresql", reason="Row Level Security only exists on PostgreSQL (CI runs it)"
)
def test_no_policy_opens_a_syllabus_or_coverage_table_to_the_data_api():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT tablename, policyname FROM pg_policies WHERE schemaname = 'public' AND tablename = ANY(%s)",
            [TABLES],
        )
        assert cursor.fetchall() == []
