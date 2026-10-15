# F-13 Today: beta rollout runbook

Flag `today_plan` stays **off** until you open the cohort. Everything below is safe to do with the flag off.

## 1. Before the beta
1. Run `pnpm check` and `pnpm lint:api && pnpm test:api` on the real repo.
2. Deploy; run `python manage.py migrate` (no new migration in W6) and `python manage.py rebuild_coverage` once.
3. Set `TODAY_TICK_SECRET` (long random string) in the API environment.
4. Schedule the tick every 5 minutes (Vercel cron, pg_cron or any scheduler): `POST /api/v1/today/internal/tick/` with header `X-Today-Tick-Secret: <secret>` (or `Authorization: Bearer <secret>`). It is idempotent and has a budget of about 20 s, so overlapping calls are safe. It runs whatever the flag says.
5. Check the response: it reports pregenerated, closed and pruned counts.

### 1a. Scheduling the tick in Zoho Catalyst (step by step)
1. Generate the secret: `openssl rand -hex 32` (it may equal `RECALL_TICK_SECRET`; a separate value is cleaner).
2. Set `TODAY_TICK_SECRET=<value>` on the API host and redeploy. An empty value refuses every caller.
3. Test by hand: `curl -i -X POST https://<api-host>/api/v1/today/internal/tick/ -H "X-Today-Tick-Secret: <value>"`. 200 with counts is good; 401/403 is a wrong secret; 404 means W6 is not deployed.
4. Catalyst console, your project, Serverless, Cron, Create Cron. Name `today-tick`; schedule `*/5 * * * *` (UTC); target Webhook (HTTP).
5. URL `https://<api-host>/api/v1/today/internal/tick/`, method `POST`, header `X-Today-Tick-Secret: <value>` (or `Authorization: Bearer <value>`), empty body. Save and enable.
6. Check the first run in the Catalyst execution log (200) and in the API logs. Keep only one Today cron (no Vercel cron for it).

## 2. What the tick does
- Pregenerates tomorrow's plan for students who opened a plan in the last 8 days (only when the flag is on for them).
- Close sweep: a plan closes 3 hours after its day ends in the student's time zone. Open provider tasks expire (counted as skipped); open own tasks carry to the next day, at most 3 times, then expire.
- Prune: evidence 90 days, tasks 13 months, empty plans 24 months.
- Emits `today_day_closed` once per plan.

## 3. Opening the cohort
1. Enable `today_plan` for about 50 students; keep a 10% holdout that does not see Today.
2. Watch for a week: `today_opened`, `today_task_completed`, `today_plan_generated`, `provider_failed`, and the share of days with at least one tick.
3. Stop and switch the flag off if `provider_failed` rises, or opens drop against the holdout.

## 4. Analytics
Events come from `event_schema.json` (API and web copies are identical and tested). Never sent: title, task_reason_text, notes. The API sink is a log line until a PostHog server client is set with `analytics.set_sink`.

## 5. Support FAQ
- **Plan looks old / offline banner:** the app shows the saved plan with its age; Refresh when back online. Ticks made offline sync automatically.
- **"A new day started":** the page was open past midnight; press Show today.
- **Task keeps coming back:** after 3 carries it asks Keep, Snooze or Delete.
- **Reset or turn things off:** `/app/settings/today` (minutes per day, focus papers, hidden kinds, tomorrow preview, celebration, lite mode, reset).
- **Account deletion/export:** handled by the `today` eraser and exporter.

## 6. Rollback
Switch `today_plan` off. Data is kept; the tick still closes and prunes safely.
