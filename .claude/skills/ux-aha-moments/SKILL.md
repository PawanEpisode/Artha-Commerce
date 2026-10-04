---
name: ux-aha-moments
description: Use when designing screens or flows. Principles for intuitive, modern, delightful UX for exam-prep students, centred on fast time-to-value.
---

# UX principles for ArthaCommerce

Audience: stressed, time-poor students, mostly on mobile, often at night. The product should feel calm, clear and rewarding.

1. **Time to value under 60 seconds.** Show something useful before asking for anything. The landing planner demo works without sign-in; first-run onboarding asks only course, level and exam date, then shows a real plan immediately.
2. **One primary action per screen.** Make "what do I do today?" the hero of the dashboard.
3. **Progress is visible and honest.** Rings, bars and streaks update instantly with motion. Never invent numbers or testimonials.
4. **Progressive disclosure.** Defaults first, advanced options behind a tap.
5. **Mobile first.** Thumb-reachable actions, 44px targets, bottom sheets over modals, no hover-only features.
6. **Calm visual tone.** Generous whitespace, one accent per view, motion only to explain change. Respect reduced motion.
7. **Forgiving.** Undo over confirm dialogs, autosave, resume where you left off.
8. **Everything has a URL.** Shareable and bookmarkable: `/courses/ca/intermediate`, later `/app/planner`, `/app/tracker/advanced-accounting`.
9. **Language.** Plain English, exam terms students already use (attempt, RTP, MTP, amendments). Indian formats: 12-month dates `2 May 2027`, thousands as `1,00,000` (`toLocaleString('en-IN')`).
10. **Aha moments to design for:** first generated plan, first completed chapter updating readiness, first streak milestone, first AI answer linked to the syllabus.

Instrument each aha moment with a PostHog event so activation can be measured.

## Every moment must work everywhere

An aha moment that breaks in Dark, on a 320 px phone or without a mouse is not shipped. Check it against `.claude/skills/ui-quality-checklist` (themes, accessibility, devices) before calling it done.
