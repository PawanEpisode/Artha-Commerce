"""The weekly email's words, its escaping, the signed unsubscribe token and the brand colours (FR-N13)."""

import re
from datetime import date
from pathlib import Path

from modules.notifications.domain import email_brand
from modules.notifications.domain.email_copy import (
    SUBJECT_LIMIT,
    EmailLinks,
    build_subject,
    build_weekly_email,
    format_duration,
)
from modules.notifications.domain.unsubscribe import make_token, read_token
from modules.notifications.domain.weekly import WeeklyFacts

LINKS = EmailLinks(
    app="https://app.test/app",
    settings="https://app.test/app/settings/notifications",
    unsubscribe="https://api.test/u?t=abc",
)
FIRST, LAST = date(2026, 10, 5), date(2026, 10, 11)


def facts(**changes):
    base = dict(
        study_seconds=19200, active_days=5, streak_days=4, coverage_pct=41.6, due_for_revision=3, days_to_exam=62
    )
    return WeeklyFacts(**{**base, **changes})


def test_durations_read_naturally():
    assert format_duration(19200) == "5 h 20 min"
    assert format_duration(2700) == "45 min"
    assert format_duration(7200) == "2 h"
    assert format_duration(0) == "0 min"
    assert format_duration(-5) == "0 min"


def test_subject_leads_with_study_time_or_with_revision_when_there_was_none():
    assert build_subject(facts()) == "Your week: 5 h 20 min of study"
    assert build_subject(facts(study_seconds=0, due_for_revision=1)) == "Your week: 1 chapter waiting for revision"
    assert len(build_subject(facts())) <= SUBJECT_LIMIT


def test_email_lists_all_four_facts_and_the_exam():
    mail = build_weekly_email(facts(), first=FIRST, last=LAST, links=LINKS)
    for line in ("5 h 20 min across 5 days", "4 days", "42%", "3 chapters", "62 days"):
        assert line in mail.text
        assert line in mail.html
    assert "5 Oct to 11 Oct" in mail.text
    assert LINKS.unsubscribe in mail.text and LINKS.unsubscribe in mail.html


def test_optional_rows_are_left_out_when_unknown():
    mail = build_weekly_email(facts(coverage_pct=None, days_to_exam=None), first=FIRST, last=LAST, links=LINKS)
    assert "Syllabus covered" not in mail.text
    assert "Exam in" not in mail.text


def test_a_week_without_study_is_kind_not_shaming():
    mail = build_weekly_email(facts(study_seconds=0, active_days=0, streak_days=0), first=FIRST, last=LAST, links=LINKS)
    assert "that is fine" in mail.text


def test_links_are_escaped_in_html():
    links = EmailLinks(app='https://x.test/?a=1&b="2"', settings="https://x.test/s", unsubscribe="https://x.test/u")
    mail = build_weekly_email(facts(), first=FIRST, last=LAST, links=links)
    assert "&amp;b=&quot;2&quot;" in mail.html
    assert 'b="2"' not in mail.html


def test_token_round_trips_and_rejects_tampering():
    token = make_token("secret", user_id="user-1", category="progress")
    assert read_token("secret", token) == ("user-1", "progress")
    assert read_token("other", token) is None
    payload, signature = token.split(".")
    assert read_token("secret", f"{payload}x.{signature}") is None
    assert read_token("secret", f"{payload}.{signature[:-1]}A") is None


def test_malformed_tokens_are_rejected_not_raised():
    for bad in ("", "nodot", ".", "a.b", "%%%.%%%", "é.é"):
        assert read_token("secret", bad) is None


def test_brand_matches_the_email_templates_package():
    source = Path(__file__).resolve().parents[5] / "packages/email-templates/src/brand.ts"
    text = source.read_text()
    for mode, ours in (("light", email_brand.LIGHT), ("dark", email_brand.DARK)):
        block = re.search(mode + r": \{(.*?)\}", text, re.S).group(1)
        theirs = dict(re.findall(r"(\w+): '(#[0-9a-fA-F]{6})'", block))
        assert theirs == ours
    assert f"name: '{email_brand.NAME}'" in text
    assert f"tagline: '{email_brand.TAGLINE}'" in text


def test_email_policy_order_and_reasons():
    from datetime import UTC, datetime, timedelta

    from modules.notifications.domain.email_policy import EmailPolicyInput, decide_email
    from modules.notifications.domain.enums import SuppressReason

    now = datetime(2026, 10, 11, 12, 30, tzinfo=UTC)
    ok = EmailPolicyInput(now=now, channel_enabled=True, has_address=True)
    assert decide_email(ok).send
    assert decide_email(EmailPolicyInput(**{**ok.__dict__, "event_disabled": True, "master_on": False})).reason is (
        SuppressReason.FLAG_OFF
    )
    assert decide_email(EmailPolicyInput(**{**ok.__dict__, "master_on": False})).reason is SuppressReason.PREFERENCE
    assert (
        decide_email(EmailPolicyInput(**{**ok.__dict__, "channel_enabled": False})).reason is SuppressReason.PREFERENCE
    )
    gone = EmailPolicyInput(**{**ok.__dict__, "has_address": False, "expires_at": now - timedelta(hours=1)})
    assert decide_email(gone).reason is SuppressReason.NO_ADDRESS
    assert decide_email(EmailPolicyInput(**{**ok.__dict__, "expires_at": now})).reason is SuppressReason.STALE
