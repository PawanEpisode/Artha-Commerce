"""
What the weekly email says, as subject, plain text and HTML (X-01.1 W3.5, FR-N13). Pure: the counts, the links and the
time all come in as arguments. Voice: warm, specific, never shaming, no emoji. Every dynamic value is escaped in HTML.
The layout is the same bulletproof table layout as the auth emails (`packages/email-templates`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from html import escape

from . import email_brand as brand
from .weekly import WeeklyFacts

_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
SUBJECT_LIMIT = 78


@dataclass(frozen=True)
class EmailContent:
    subject: str
    preheader: str
    text: str
    html: str


@dataclass(frozen=True)
class EmailLinks:
    app: str  # where the button goes
    settings: str  # notification settings
    unsubscribe: str  # the signed one-click link


def _plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def format_duration(seconds: int) -> str:
    """`5 h 20 min`, `45 min`, `0 min`. Seconds are dropped: a week is not measured to the second."""
    minutes = max(seconds, 0) // 60
    hours, rest = divmod(minutes, 60)
    if hours and rest:
        return f"{hours} h {rest} min"
    return f"{hours} h" if hours else f"{rest} min"


def _day(value: date) -> str:
    return f"{value.day} {value.strftime('%b')}"


def build_subject(facts: WeeklyFacts) -> str:
    if facts.study_seconds > 0:
        subject = f"Your week: {format_duration(facts.study_seconds)} of study"
    else:
        subject = f"Your week: {_plural(facts.due_for_revision, 'chapter')} waiting for revision"
    return subject[:SUBJECT_LIMIT]


def _rows(facts: WeeklyFacts) -> list[tuple[str, str]]:
    rows = [
        ("Study time", f"{format_duration(facts.study_seconds)} across {_plural(facts.active_days, 'day')}"),
        ("Streak", _plural(facts.streak_days, "day")),
    ]
    if facts.coverage_pct is not None:
        rows.append(("Syllabus covered", f"{round(facts.coverage_pct)}%"))
    rows.append(("Due for revision", _plural(facts.due_for_revision, "chapter")))
    if facts.days_to_exam is not None:
        rows.append(("Exam in", _plural(facts.days_to_exam, "day")))
    return rows


def _intro(facts: WeeklyFacts) -> str:
    if facts.study_seconds > 0:
        return "Here is how your week went. Small, steady days add up."
    return "You did not log study time this week, and that is fine. Here is where things stand."


def build_weekly_email(facts: WeeklyFacts, *, first: date, last: date, links: EmailLinks) -> EmailContent:
    subject = build_subject(facts)
    heading = "Your week in Artha"
    period = f"{_day(first)} to {_day(last)}"
    rows = _rows(facts)
    intro = _intro(facts)
    preheader = f"{period}. {rows[0][1]}."
    button = "Open Artha"

    text_rows = "\n".join(f"{label}: {value}" for label, value in rows)
    text = (
        f"{heading} ({period})\n\n{intro}\n\n{text_rows}\n\n{button}: {links.app}\n\n"
        f"You get this because the weekly summary is on in your notification settings: {links.settings}\n"
        f"Unsubscribe from the weekly summary: {links.unsubscribe}\n\n{brand.NAME}. {brand.TAGLINE}.\n"
    )
    return EmailContent(subject, preheader, text, _html(heading, period, intro, rows, button, links, preheader))


def _html(heading, period, intro, rows, button, links: EmailLinks, preheader) -> str:
    light, dark = brand.LIGHT, brand.DARK
    e = escape
    table_rows = "\n".join(
        f'<tr><td class="muted" style="padding:10px 0;border-top:1px solid {light["border"]};font-size:14px;'
        f'line-height:20px;color:{light["muted"]};">{e(label)}</td>'
        f'<td class="text row" align="right" style="padding:10px 0;border-top:1px solid {light["border"]};'
        f'font-size:16px;line-height:24px;font-weight:700;color:{light["text"]};">{e(value)}</td></tr>'
        for label, value in rows
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <meta name="supported-color-schemes" content="light dark">
  <title>{e(heading)}</title>
  <style>
    @media (prefers-color-scheme: dark) {{
      .page {{ background: {dark["page"]} !important; }}
      .card {{ background: {dark["card"]} !important; border-color: {dark["border"]} !important; }}
      .text {{ color: {dark["text"]} !important; }}
      .muted {{ color: {dark["muted"]} !important; }}
      .link {{ color: {dark["primary"]} !important; }}
      .btn {{ background: {dark["primary"]} !important; }}
      .btn-link {{ color: {dark["onPrimary"]} !important; }}
      .row {{ border-color: {dark["border"]} !important; }}
    }}
    @media only screen and (max-width: 520px) {{
      .inner {{ padding: 28px 20px !important; }}
    }}
  </style>
</head>
<body class="page" style="margin:0;padding:0;background:{light["page"]};font-family:{_FONT};">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{e(preheader)}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" class="page" style="background:{light["page"]};">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;">
          <tr>
            <td style="padding:0 4px 20px;">
              <span class="text" style="font-size:20px;font-weight:800;letter-spacing:-0.3px;color:{light["text"]};">{e(brand.NAME)}</span>
            </td>
          </tr>
          <tr>
            <td class="card" style="background:{light["card"]};border:1px solid {light["border"]};border-radius:16px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td class="inner" style="padding:36px 36px 28px;">
                    <h1 class="text" style="margin:0 0 4px;font-size:24px;line-height:32px;font-weight:800;color:{light["text"]};">{e(heading)}</h1>
                    <p class="muted" style="margin:0 0 16px;font-size:13px;line-height:20px;color:{light["muted"]};">{e(period)}</p>
                    <p class="text" style="margin:0 0 20px;font-size:16px;line-height:26px;color:{light["text"]};">{e(intro)}</p>
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin:0 0 24px;">
{table_rows}
                    </table>
                    <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:8px 0 8px;">
                      <tr>
                        <td class="btn" bgcolor="{light["primary"]}" style="border-radius:10px;background:{light["primary"]};">
                          <a href="{e(links.app)}" class="btn-link" style="display:inline-block;padding:14px 28px;font-size:16px;font-weight:700;line-height:20px;color:{light["onPrimary"]};text-decoration:none;border-radius:10px;">{e(button)}</a>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 8px 0;">
              <p class="muted" style="margin:0 0 6px;font-size:12px;line-height:18px;color:{light["muted"]};">You get this because the weekly summary is on in your <a href="{e(links.settings)}" class="link" style="color:{light["primary"]};">notification settings</a>. <a href="{e(links.unsubscribe)}" class="link" style="color:{light["primary"]};">Unsubscribe from the weekly summary</a>.</p>
              <p class="muted" style="margin:0;font-size:12px;line-height:18px;color:{light["muted"]};">{e(brand.NAME)}. {e(brand.TAGLINE)}.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""
