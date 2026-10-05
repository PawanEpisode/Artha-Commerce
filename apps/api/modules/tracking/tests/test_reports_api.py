import uuid
from datetime import timedelta

import pytest

from modules.coverage.models import ChapterProgress
from modules.syllabus.models import ExamTerm
from modules.tracking.models import DailyRollup

from .conftest import NOW, ist, manual

pytestmark = pytest.mark.django_db

RANGE = "from=2026-09-28&to=2026-10-04"


@pytest.fixture
def data(api, ids):
    """Last week (Mon 28 Sep to Sun 4 Oct): Taxation 3 h + 1 h, Laws 2 h, an untagged hour, spread over four days."""
    manual(
        api,
        ist(28, 20, month=9),
        ist(28, 23, month=9),
        subject_id=ids["taxation"],
        chapter_id=ids["gst"],
        activity_type="reading",
    )
    manual(
        api,
        ist(29, 9, month=9),
        ist(29, 10, month=9),
        subject_id=ids["taxation"],
        chapter_id=ids["residential"],
        activity_type="practice",
    )
    manual(api, ist(30, 21, month=9), ist(30, 23, month=9), subject_id=ids["laws"], activity_type="revision")
    manual(api, ist(2, 6), ist(2, 7))
    return ids


def test_summary_tiles_equal_the_sum_of_sessions(api, data):
    s = api.get(f"/tracking/reports/summary/?{RANGE}").json_body
    assert s["total_seconds"] == 7 * 3600 and s["days_studied"] == 4 and s["sessions"] == 4
    assert s["average_seconds_per_studied_day"] == round(7 * 3600 / 4)
    assert s["longest_day"] == {"date": "2026-09-28", "seconds": 3 * 3600}
    assert s["longest_session_seconds"] == 3 * 3600
    assert "previous" not in s


def test_summary_compares_with_the_previous_period(api, data):
    manual(api, ist(21, 8, month=9), ist(21, 10, month=9))  # the week before: 2 h
    s = api.get(f"/tracking/reports/summary/?{RANGE}&compare=1").json_body
    assert s["previous"]["total_seconds"] == 7200 and (s["previous"]["from"], s["previous"]["to"]) == (
        "2026-09-21",
        "2026-09-27",
    )
    assert s["change"] == {"seconds": 7 * 3600 - 7200, "percent": 250}


def test_summary_of_an_empty_range_is_zeros_not_fake_numbers(api):
    s = api.get(f"/tracking/reports/summary/?{RANGE}").json_body
    assert (s["total_seconds"], s["days_studied"], s["sessions"], s["longest_day"]) == (0, 0, 0, None)


def test_series_by_day_week_and_month_with_empty_buckets(api, data):
    days = api.get(f"/tracking/reports/series/?{RANGE}&group=day").json_body
    assert [b["seconds"] for b in days["buckets"]] == [10800, 3600, 7200, 0, 3600, 0, 0]
    weeks = api.get("/tracking/reports/series/?from=2026-09-01&to=2026-10-04&group=week").json_body
    assert [b["start"] for b in weeks["buckets"]] == [
        "2026-08-31",
        "2026-09-07",
        "2026-09-14",
        "2026-09-21",
        "2026-09-28",
    ]
    assert weeks["buckets"][-1]["seconds"] == 7 * 3600
    months = api.get("/tracking/reports/series/?from=2026-09-15&to=2026-10-05&group=month").json_body
    assert [(b["start"], b["seconds"]) for b in months["buckets"]] == [("2026-09-01", 6 * 3600), ("2026-10-01", 3600)]


def test_series_by_subject_has_a_legend_and_parts_that_add_up(api, data):
    s = api.get(f"/tracking/reports/series/?{RANGE}&group=week&by=subject").json_body
    bucket = s["buckets"][0]
    assert sum(bucket["parts"].values()) == bucket["seconds"]
    assert {item["name"] for item in s["legend"]} == {"Taxation", "Corporate and Other Laws", "Untagged"}
    assert api.get(f"/tracking/reports/series/?{RANGE}&by=source").json_body["legend"] == [
        {"key": "manual", "name": "Manual"}
    ]


def test_week_start_setting_moves_the_weeks(api, data):
    api.put("/tracking/settings/", {"week_start": 0})
    s = api.get("/tracking/reports/series/?from=2026-09-28&to=2026-10-04&group=week").json_body
    assert s["buckets"][0]["start"] == "2026-09-27" and s["week_start"] == 0


def test_breakdown_by_subject_chapter_activity_and_source(api, data):
    b = api.get(f"/tracking/reports/breakdown/?{RANGE}&by=subject").json_body
    assert b["total_seconds"] == 7 * 3600
    assert [(i["name"], i["seconds"], i["share_percent"]) for i in b["items"]] == [
        ("Taxation", 4 * 3600, 57.1),
        ("Corporate and Other Laws", 2 * 3600, 28.6),
        ("Untagged", 3600, 14.3),
    ]
    tax_id = b["items"][0]["subject_id"]
    chapters = api.get(f"/tracking/reports/breakdown/?{RANGE}&by=chapter&parent_id={tax_id}").json_body
    assert [(i["name"], i["seconds"]) for i in chapters["items"]] == [
        ("GST: Input Tax Credit", 10800),
        ("Residential status", 3600),
    ]
    act = api.get(f"/tracking/reports/breakdown/?{RANGE}&by=activity").json_body["items"]
    assert {i["key"]: i["seconds"] for i in act} == {
        "reading": 10800,
        "practice": 3600,
        "revision": 7200,
        "other": 3600,
    }
    assert api.get(f"/tracking/reports/breakdown/?{RANGE}&by=source").json_body["items"][0]["key"] == "manual"


def test_breakdown_rolls_up_to_groups_and_levels(api, data):
    groups = api.get(f"/tracking/reports/breakdown/?{RANGE}&by=group").json_body["items"]
    assert [(i["name"], i["seconds"]) for i in groups] == [
        ("Group I", 4 * 3600),
        ("Group II", 2 * 3600),
        ("Untagged", 3600),
    ]
    level = api.get(f"/tracking/reports/breakdown/?{RANGE}&by=level").json_body["items"]
    assert level[0]["name"] == "CA Intermediate" and level[0]["seconds"] == 6 * 3600
    assert api.get(f"/tracking/reports/breakdown/?{RANGE}&by=colour").status_code == 400


def test_a_subject_keeps_its_history_across_a_scheme_change(api, data):
    """Reports group by the subject's stable key, so Taxation under the 2023 and 2025 schemes is one row."""
    from modules.syllabus.models import Scheme, Subject
    from modules.syllabus.services import publish_scheme, retire_scheme
    from modules.syllabus.tests.helpers import make_scheme

    retire_scheme(Scheme.objects.get(code="2023"))
    new = make_scheme(code="2025", publish=False)
    publish_scheme(new)
    new_tax = Subject.objects.get(scheme=new, key="taxation")
    assert manual(api, ist(1, 8), ist(1, 9), subject_id=str(new_tax.id)).status_code == 201
    items = api.get("/tracking/reports/breakdown/?from=2026-09-28&to=2026-10-05&by=subject").json_body["items"]
    assert [(i["name"], i["seconds"]) for i in items if i["name"] == "Taxation"] == [("Taxation", 5 * 3600)]
    # and the chapter drill-down merges the same chapter across both schemes
    chapters = api.get("/tracking/reports/breakdown/?from=2026-09-28&to=2026-10-05&by=chapter").json_body["items"]
    assert len([i for i in chapters if i["name"] == "GST: Input Tax Credit"]) == 1


def test_heatmap_lists_studied_days_with_intensity(api, data):
    h = api.get("/tracking/reports/heatmap/?from=2026-09-01&to=2026-10-05").json_body
    assert [(d["date"], d["seconds"], d["level"]) for d in h["days"]] == [
        ("2026-09-28", 10800, 4),
        ("2026-09-29", 3600, 2),
        ("2026-09-30", 7200, 3),
        ("2026-10-02", 3600, 2),
    ]
    assert api.get("/tracking/reports/heatmap/?from=2024-01-01&to=2026-10-05").status_code == 400  # over 366 days


def test_default_heatmap_covers_a_year(api, data):
    h = api.get("/tracking/reports/heatmap/").json_body
    assert (h["from"], h["to"]) == ("2025-10-06", "2026-10-05") and len(h["days"]) == 4


def test_best_hours_and_weekday_pattern(api, data):
    r = api.get("/tracking/reports/hours/?from=2026-09-01&to=2026-10-05").json_body
    assert len(r["hours"]) == 24 and sum(r["hours"]) == 7 * 3600 and r["approximate"] is True
    assert (
        r["hours"][20] == 3600 and r["hours"][21] == r["hours"][22] == 7200 and r["hours"][9] == r["hours"][6] == 3600
    )
    mon = r["weekdays"][0]
    assert (mon["weekday"], mon["seconds"], mon["days"]) == (0, 3 * 3600, 1)


def test_time_vs_coverage_flags_chapters(api, data, ids, scheme):
    term = ExamTerm.objects.get(level__course__code="ca", level__code="intermediate", code="2027-05")
    assert (
        api.post("/coverage/enrollments/", {"scheme": str(scheme.id), "target_term": str(term.id)}).status_code == 201
    )
    ChapterProgress.objects.filter(chapter_id=ids["gst"]).update(coverage_pct=20)
    r = api.get(f"/tracking/reports/time-vs-coverage/?subject_id={ids['taxation']}&{RANGE}").json_body
    rows = {c["name"]: c for c in r["chapters"]}
    assert rows["GST: Input Tax Credit"]["seconds"] == 10800 and rows["GST: Input Tax Credit"]["coverage_percent"] == 20
    assert rows["GST: Input Tax Credit"]["flag"] == "high_time_low_coverage"
    assert rows["Heads of income"]["flag"] == "low_time_low_coverage"
    assert api.get(f"/tracking/reports/time-vs-coverage/?{RANGE}").status_code == 400
    assert api.get(f"/tracking/reports/time-vs-coverage/?subject_id={uuid.uuid4()}&{RANGE}").status_code == 404


def test_weekly_summary_for_the_previous_week(api, data, clock):
    clock.set(NOW - timedelta(days=7))  # the goals were set on Monday 28 September, so they applied to that week
    api.put(
        "/tracking/goals/",
        {
            "goals": [
                {"period": "weekly", "target_minutes": 6 * 60},
                {"period": "weekly", "subject_id": data["laws"], "target_minutes": 5 * 60},
            ]
        },
    )
    clock.set(NOW)
    w = api.get("/tracking/reports/weekly-summary/").json_body
    assert (w["week_start"], w["week_end"]) == ("2026-09-28", "2026-10-04")
    assert w["total_seconds"] == 7 * 3600 and w["days_tracked"] == 4
    assert w["best_day"]["date"] == "2026-09-28" and w["top_subject"] == {"name": "Taxation", "seconds": 4 * 3600}
    assert w["goal"] == {"target_minutes": 360, "met": True, "done_seconds": 7 * 3600}
    assert (
        w["suggestion"]["kind"] == "subject_shortfall" and w["suggestion"]["subject_name"] == "Corporate and Other Laws"
    )
    assert w["suggestion"]["remaining_seconds"] == 3 * 3600


def test_ranges_are_limited(api):
    assert api.get("/tracking/reports/series/?from=2025-01-01&to=2026-10-04&group=day").status_code == 400
    assert api.get("/tracking/reports/series/?from=2026-10-04&to=2026-09-01").status_code == 400
    assert api.get("/tracking/reports/series/?from=2000-01-01&to=2026-10-04&group=month").status_code == 400
    assert api.get("/tracking/reports/series/?group=year").status_code == 400
    assert api.get("/tracking/reports/summary/?from=nonsense").status_code == 400


def test_reports_are_private_to_the_student(api, other_api, data):
    assert other_api.get(f"/tracking/reports/summary/?{RANGE}").json_body["total_seconds"] == 0
    assert other_api.get(f"/tracking/reports/breakdown/?{RANGE}&by=subject").json_body["items"] == []
    assert other_api.get("/tracking/reports/heatmap/").json_body["days"] == []


def test_etag_gives_a_304_until_something_changes(api, data):
    url = f"/api/v1/tracking/reports/summary/?{RANGE}"
    first = api.c.get(url)
    etag = first["ETag"]
    assert first.status_code == 200 and first["Cache-Control"] == "private, no-cache"
    assert api.c.get(url, HTTP_IF_NONE_MATCH=etag).status_code == 304
    manual(api, ist(3, 9), ist(3, 10))
    changed = api.c.get(url, HTTP_IF_NONE_MATCH=etag)
    assert changed.status_code == 200 and changed["ETag"] != etag


def test_etag_also_changes_when_a_session_is_deleted_or_settings_change(api, data):
    url = f"/api/v1/tracking/reports/series/?{RANGE}&group=week"
    etag = api.c.get(url)["ETag"]
    api.put("/tracking/settings/", {"week_start": 0})
    etag2 = api.c.get(url)["ETag"]
    assert etag2 != etag
    sid = manual(api, ist(3, 9), ist(3, 10)).json_body["id"]
    etag3 = api.c.get(url)["ETag"]
    api.delete(f"/tracking/sessions/{sid}/")
    assert api.c.get(url)["ETag"] not in {etag3}
    api.put("/tracking/goals/", {"goals": [{"period": "daily", "target_minutes": 90}]})
    assert api.c.get(url)["ETag"] != api.c.get(url + "&x=1")["ETag"]  # parameters are part of the tag


def test_csv_export_of_sessions_and_the_aggregate(api, data):
    sid = manual(api, ist(3, 9), ist(3, 10), note="=HYPERLINK(1)").json_body["id"]
    res = api.c.get(f"/api/v1/tracking/sessions/export.csv?{RANGE}")
    body = b"".join(res.streaming_content).decode()
    assert res["Content-Type"].startswith("text/csv") and "attachment" in res["Content-Disposition"]
    lines = body.strip().splitlines()
    assert lines[0].startswith("date,start,end,minutes,source") and len(lines) == 6 and "HYPERLINK" not in body
    with_notes = b"".join(
        api.c.get(
            "/api/v1/tracking/sessions/export.csv?from=2026-10-03&to=2026-10-03&include_notes=1"
        ).streaming_content
    ).decode()
    assert "'=HYPERLINK(1)" in with_notes  # formulas are neutralised
    agg = (
        b"".join(api.c.get(f"/api/v1/tracking/reports/export.csv?{RANGE}&by=subject").streaming_content)
        .decode()
        .splitlines()
    )
    assert agg[0] == "subject,minutes,share_percent,sessions" and agg[1].startswith("Taxation,240.0")
    assert sid


def test_exports_are_throttled(api, data):
    codes = [api.c.get("/api/v1/tracking/sessions/export.csv").status_code for _ in range(8)]
    assert codes[:6] == [200] * 6 and codes[6] == 429


def test_rebuild_matches_the_incremental_rollups(api, data):
    from django.core.management import call_command

    from modules.tracking.models import HourBucket

    before = sorted(
        DailyRollup.objects.values_list("study_date", "subject_id", "chapter_id", "seconds", "sessions"), key=str
    )
    hours = sorted(HourBucket.objects.values_list("study_date", "hour", "seconds"))
    DailyRollup.objects.all().delete()
    HourBucket.objects.all().delete()
    call_command("rebuild_tracking_rollups")
    assert (
        sorted(
            DailyRollup.objects.values_list("study_date", "subject_id", "chapter_id", "seconds", "sessions"), key=str
        )
        == before
    )
    assert sorted(HourBucket.objects.values_list("study_date", "hour", "seconds")) == hours
    assert NOW


def test_data_export_and_delete(api, other_api, data):
    api.put("/tracking/goals/", {"goals": [{"period": "daily", "target_minutes": 90}]})
    exported = api.get("/tracking/data/").json_body
    assert len(exported["sessions"]) == 4 and len(exported["goals"]) == 1
    manual(other_api, ist(3, 9), ist(3, 10))
    assert api.delete("/tracking/data/").status_code == 204
    assert api.get("/tracking/data/").json_body["sessions"] == []
    assert not DailyRollup.objects.filter(user_id=exported["sessions"][0]["user_id"]).exists()
    assert len(other_api.get("/tracking/data/").json_body["sessions"]) == 1  # nobody else's data is touched
