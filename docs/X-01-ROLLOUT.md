# X-01 Notifications, floating timer, keep awake: build and rollout runbook

Companion to `docs/product/prd/X-01.1-push-notifications.md` (waves, requirements) and `docs/product/erd/X-01.1-push-notifications.md` (tables). Same style as the other `docs/*-ROLLOUT.md` files, but organised **phase by phase** with the exact steps and commands, split into **web**, **api** and **other tools**. Phases and waves use the numbering in PRD section 0 and 13.

| Phase | What | Flags |
| --- | --- | --- |
| P1 | Spikes on real devices | none |
| P2 | Alerts core (waves W2.1 to W2.7), includes keep awake | `push_notifications`, `keep_awake` |
| P3 | More alerts (waves W3.1 to W3.7) | `push_notifications` |
| P4 | Floating timer | `floating_timer` |
| P5 | Desktop companion, only if the gate passes | `desktop_companion` |

Do the phases in order. A phase starts only when the gate before it is met (PRD 13.2).

## 0. Conventions used in every phase

All commands run from your Mac in a terminal. `ROOT` is the repository.

```bash
export ROOT=~/Desktop/personal-work/ArthaCommerce
cd "$ROOT"
```

**Start every wave the same way** (one branch and one pull request per wave):

```bash
cd "$ROOT"
pgrep -x git >/dev/null || find .git -maxdepth 3 -name "*.lock" -print -delete   # clears a stale lock, see CLAUDE.md
git switch main && git pull --ff-only
git switch -c feat/x-01-<wave>-<short-name>        # example: feat/x-01-w2-1-notifications-foundation
pnpm install
```

**API environment (once per machine)**

```bash
cd "$ROOT/apps/api"
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
# Real Postgres for tests that need it (CI uses postgres:16). Skip if you already have one.
docker run -d --name artha-pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:16
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres
export DJANGO_DEBUG=true
```

Reopen the venv in a new terminal with `cd "$ROOT/apps/api" && source .venv/bin/activate`. `DATABASE_URL` must be exported in each terminal that runs `migrate`, `pytest` or the server.

**Finish every wave the same way**

```bash
cd "$ROOT"
pnpm check                                                   # typecheck, lint, format, contrast, emails, web tests, build
cd apps/api && pytest && ruff check . && ruff format --check . && cd "$ROOT"
git add -A
git commit -m "feat(api): <what this wave does>"             # Conventional Commits; scopes: web, api, ds, docs, ci, deps, db, product, tooling
git push -u origin HEAD
gh pr create --base main --fill                              # CI repeats every check
```

Never use `--no-verify`. If a hook fails, fix the cause. Dependency additions go in their own commit: `chore(deps): add pywebpush, qstash and cryptography`.

## 1. Accounts, keys and variables (once, before P2)

| Item | Where to get it | Goes to | Secret |
| --- | --- | --- | --- |
| VAPID key pair | Command below | public key: web as `VITE_VAPID_PUBLIC_KEY`; private key: API as `VAPID_PRIVATE_KEY` | private key yes |
| `VAPID_SUBJECT` | A role address you control, written `mailto:alerts@<your-domain>`. Push services see it, so do not use a personal address | API | no |
| `FIELD_ENCRYPTION_KEYS` | Command below (one key now; more later when rotating) | API | yes |
| `FIELD_HASH_PEPPER` | `openssl rand -hex 32` | API | yes |
| `CRON_SECRET` | `openssl rand -hex 32` | API, and the Supabase vault (P2 W2.7) | yes |
| `QSTASH_TOKEN`, `QSTASH_CURRENT_SIGNING_KEY`, `QSTASH_NEXT_SIGNING_KEY` | Upstash console, QStash tab (create a free account first) | API | yes |
| `QSTASH_URL` | Only if your QStash region is not the default; shown in the same tab | API | no |
| `NOTIFICATIONS_ENABLED` | Set to `false` until the staged rollout (section 4) | API | no |
| `NOTIFICATIONS_QUEUE` | `qstash` in production and preview; `null` locally unless you test the queue | API | no |
| `NOTIFICATIONS_PUBLIC_BASE_URL` | The API's public origin, the same as `VITE_API_URL`, with no trailing slash. QStash calls it and the signature check uses it | API | no |
| `NOTIFICATIONS_DISABLED_EVENTS` | Empty. A comma list of event keys to stop without a deploy of code (needs a redeploy of env) | API | no |
| PostHog flags | Section below | PostHog | no |

Generate the values:

```bash
# VAPID key pair (copy both values somewhere safe, for example your password manager)
npx --yes web-push generate-vapid-keys --json

# Field encryption key
cd "$ROOT/apps/api" && source .venv/bin/activate
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Pepper and cron secret (run twice, use one value for each)
openssl rand -hex 32
```

Put secrets into the **Vercel API project** without leaving them in your shell history:

```bash
cd "$ROOT/apps/api"
npx vercel link                                   # once; choose the arthacommerce-api project
read -rs -p "VAPID_PRIVATE_KEY: " V; echo; printf '%s' "$V" | npx vercel env add VAPID_PRIVATE_KEY production; unset V
# repeat the line above for: FIELD_ENCRYPTION_KEYS, FIELD_HASH_PEPPER, CRON_SECRET,
# QSTASH_TOKEN, QSTASH_CURRENT_SIGNING_KEY, QSTASH_NEXT_SIGNING_KEY
printf '%s' 'mailto:alerts@<your-domain>' | npx vercel env add VAPID_SUBJECT production
printf '%s' 'false' | npx vercel env add NOTIFICATIONS_ENABLED production
printf '%s' 'qstash' | npx vercel env add NOTIFICATIONS_QUEUE production
printf '%s' 'https://api.<your-domain>' | npx vercel env add NOTIFICATIONS_PUBLIC_BASE_URL production
```

The dashboard works too: Vercel, project `arthacommerce-api`, Settings, Environment Variables. Repeat for **Preview** if you use preview deployments. The **web** project gets only the public key:

```bash
cd "$ROOT/apps/web"
npx vercel link                                   # choose the arthacommerce-web project
printf '%s' '<publicKey from the VAPID command>' | npx vercel env add VITE_VAPID_PUBLIC_KEY production
```

`VITE_*` values are baked in at build time, so redeploy the web project after adding one. Local files (never committed):

```bash
# apps/web/.env.local
echo 'VITE_VAPID_PUBLIC_KEY=<publicKey>' >> "$ROOT/apps/web/.env.local"
# apps/api/.env  (then: set -a; source .env; set +a)
cat >> "$ROOT/apps/api/.env" <<'ENVEOF'
NOTIFICATIONS_ENABLED=true
NOTIFICATIONS_QUEUE=null
VAPID_PRIVATE_KEY=<privateKey>
VAPID_SUBJECT=mailto:alerts@example.com
FIELD_ENCRYPTION_KEYS=<fernet key>
FIELD_HASH_PEPPER=<hex>
CRON_SECRET=<hex>
ENVEOF
```

**PostHog flags** (dashboard, Feature flags, New feature flag). Create four, all at 0% rollout with your own email as an allowed person so you can test: `push_notifications`, `keep_awake`, `floating_timer`, `desktop_companion`. Sending is fail-closed on the API: an unknown flag, a missing key or an outage means no push. Screens fail open.

Do not commit any `.env*` file; `gitleaks` runs in CI.

## 2. Phase 1: spikes (about 1 week)

Goal: turn the unknowns in the approved PRD into written go or no-go answers before they become promises. Nothing here touches the repository code.

**Other tools: build the spike page outside the repository.**

```bash
mkdir -p ~/artha-push-spike && cd ~/artha-push-spike

cat > index.html <<'HTMLEOF'
<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">
<button id="go">Subscribe</button> <button id="lock">Wake lock</button> <button id="pip">Pop out + lock</button>
<pre id="out" style="white-space:pre-wrap;word-break:break-all"></pre>
<script>
const out = document.getElementById('out')
const pub = new URLSearchParams(location.search).get('pub') || ''
const toKey = (s) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(s.length / 4) * 4, '=')), (c) => c.charCodeAt(0))
document.getElementById('go').onclick = async () => {
  const reg = await navigator.serviceWorker.register('/sw.js')
  await navigator.serviceWorker.ready
  if ((await Notification.requestPermission()) !== 'granted') return (out.textContent = 'permission: ' + Notification.permission)
  const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: toKey(pub) })
  out.textContent = JSON.stringify(sub)
}
document.getElementById('lock').onclick = async () => {
  try { const s = await navigator.wakeLock.request('screen'); out.textContent = 'lock held'; s.onrelease = () => (out.textContent += '\nreleased') }
  catch (e) { out.textContent = 'lock refused: ' + e.name }
}
document.getElementById('pip').onclick = async () => {
  if (!('documentPictureInPicture' in window)) return (out.textContent = 'no document PiP here')
  const w = await documentPictureInPicture.requestWindow({ width: 260, height: 72 })
  w.document.body.textContent = 'timer'
  try { const s = await w.navigator.wakeLock.request('screen'); out.textContent = 'lock requested from pop-out'; s.onrelease = () => (out.textContent += '\nreleased') }
  catch (e) { out.textContent = 'pop-out lock refused: ' + e.name }
}
</script>
HTMLEOF

cat > sw.js <<'JSEOF'
self.addEventListener('push', (e) => {
  const d = e.data ? e.data.json() : {}
  e.waitUntil(self.registration.showNotification(d.title || 'Test', { body: d.body, tag: d.tag }))
})
self.addEventListener('notificationclick', (e) => { e.notification.close(); e.waitUntil(clients.openWindow('/')) })
JSEOF

cat > send.py <<'PYEOF'
import json, sys
from pywebpush import webpush
sub_file, private_key = sys.argv[1], sys.argv[2]
declarative = len(sys.argv) > 3 and sys.argv[3] == "declarative"
body = {"title": "Round 2 done", "body": "25 minutes. Take 5.", "tag": "spike"}
if declarative:  # Safari 18.4+ format, check against the WebKit post linked in the PRD
    body = {"web_push": 8030, "notification": {"title": body["title"], "body": body["body"], "navigate": sys.argv[4]}}
webpush(json.load(open(sub_file)), json.dumps(body), vapid_private_key=private_key,
        vapid_claims={"sub": "mailto:alerts@example.com"}, ttl=300, headers={"Urgency": "high"})
print("accepted by the push service")
PYEOF

python3 -m venv .venv && source .venv/bin/activate && pip install "pywebpush>=2.5,<3"
```

**Serve it.** Desktop Chrome and Edge accept `localhost`. Phones need HTTPS, so use a tunnel.

```bash
cd ~/artha-push-spike && npx --yes serve -l 5173 .             # terminal 1
brew install cloudflared                                         # once
cloudflared tunnel --url http://localhost:5173                   # terminal 2, prints https://<random>.trycloudflare.com
```

Open `https://<random>.trycloudflare.com/?pub=<publicKey>` (or `http://localhost:5173/?pub=...` on desktop), tap **Subscribe**, copy the JSON shown into `sub.json`, then send:

```bash
cd ~/artha-push-spike && source .venv/bin/activate
python send.py sub.json '<privateKey from the VAPID command>'
```

This proves the generated key works with `pywebpush` (the key format is the most common first failure) and that the alert shows with the tab closed.

| Spike | Steps | Write down |
| --- | --- | --- |
| S1 Android battery savers | Open the tunnel URL in Chrome on three common phones, subscribe, close Chrome, run `send.py`; repeat with battery saver on and after 30 minutes idle | Which phones show the alert, and how late |
| S2 iPhone and iPad Home Screen | Open in Safari, Share, Add to Home Screen, open the icon, Subscribe, lock the phone, send; press **Wake lock**, leave it for the screen timeout | Does push show, does the lock hold |
| S3 Safari declarative push | On iOS 18.4+ and macOS 15.5+ run `python send.py sub.json '<key>' declarative https://<tunnel>/` with the worker file renamed so it cannot run | Does the alert show without the worker |
| S4 Visible tab and tag | With the tab visible, send two pushes with the same `tag` | One alert replaces the other, and Safari still requires a visible alert |
| S5 Queue and cron | See below | Cancel works, Supabase extensions available |
| S6 Wake lock from the pop-out | Chrome and Edge: press **Pop out + lock**, switch to another app for the screen timeout | Does the screen stay on |
| S7 Safari floating timer | Decide go or no-go on a video-based Picture-in-Picture timer (needs a one-hour experiment; default is no-go) | Decision |

**S5 commands** (QStash delay and cancel, and Supabase extensions):

```bash
# Delayed message: use any URL you can see, for example a free https://webhook.site address
curl -s -X POST "https://qstash.upstash.io/v2/publish/https://webhook.site/<your-id>" \
  -H "Authorization: Bearer $QSTASH_TOKEN" -H "Upstash-Delay: 30s" -d '{"hello":"artha"}'
# The reply has a messageId. Cancel it before the 30 seconds pass:
curl -s -X DELETE "https://qstash.upstash.io/v2/messages/<messageId>" -H "Authorization: Bearer $QSTASH_TOKEN"
```

In the Supabase SQL editor: `select name, default_version from pg_available_extensions where name in ('pg_cron','pg_net','supabase_vault');` All three should be listed. If the cancel call or the extensions fail, record it: Q2 may change to Supabase Queues.

**Record the results** (this closes gate G0):

```bash
cd "$ROOT"
cat > docs/X-01-spike-results.md <<'MDEOF'
# X-01 spike results (P1)

| Spike | Date | Devices and versions | Result (go / no-go / partial) | Notes |
| --- | --- | --- | --- | --- |
| S1 Android battery savers | | | | |
| S2 iPhone Home Screen | | | | |
| S3 Safari declarative push | | | | |
| S4 Visible tab and tag | | | | |
| S5 Queue and cron | | | | |
| S6 Wake lock from the pop-out | | | | |
| S7 Safari floating timer | | | | |
MDEOF
git switch -c docs/x-01-spike-results && git add docs/X-01-spike-results.md && git commit -m "docs(product): record the X-01 spike results"
```

Fill the table before you commit. Throw away `~/artha-push-spike` afterwards (it holds a private key if you pasted one into a file).

## 3. Phase 2: alerts core (about 5 weeks)

Deploy order for every wave that has a migration: **1) migrate production, 2) merge, 3) wait for the API deployment, then the web deployment, 4) check**. Tables and columns are always added before the code that uses them, so this order never breaks the running app.

```bash
# Production migration (new terminal, so the local DATABASE_URL is not set)
cd "$ROOT/apps/api" && source .venv/bin/activate
unset DATABASE_URL
export DJANGO_SECRET_KEY=any-value-locally
export DIRECT_DATABASE_URL='<Supabase direct connection string, Project Settings, Database>'
python manage.py migrate
```

### W2.1 Foundation (api)

Goal: module, tables, pure rules, settings endpoints, kill switches, erase and export. No web changes, nothing is sent yet.

**API**

```bash
cd "$ROOT" && git switch -c feat/x-01-w2-1-notifications-foundation
cd apps/api && source .venv/bin/activate

# 1. dependencies (own commit)
printf '%s\n' 'pywebpush>=2.5,<3' 'qstash>=3.4,<4' 'cryptography>=44' >> requirements.txt
pip install -r requirements-dev.txt
git add requirements.txt && git commit -m "chore(deps): add pywebpush, qstash and cryptography"

# 2. module skeleton (layout from PRD 9.1)
mkdir -p modules/notifications/{domain,services,selectors,channels,scheduling,views,management/commands,tests,migrations}
touch modules/notifications/{apps,models,serializers,urls,admin,subscribers,handlers,dispatch}.py
for d in "" domain services selectors channels scheduling views management management/commands tests migrations; do
  touch "modules/notifications/${d:+$d/}__init__.py"
done
```

Then, in this order (write the tests with each piece, pure code first):

1. `core/feature_flags.py`: add `flag_enabled(name, distinct_id, *, strict=False)`. With `strict=True`, a missing key, an unknown flag, a timeout or an error all return `False`. Default stays fail open, so no existing caller changes. Test both modes.
2. `core/fields.py`: `EncryptedTextField` (Fernet, `MultiFernet` over `FIELD_ENCRYPTION_KEYS`) and `hmac_hex(value)` using `FIELD_HASH_PEPPER`. Test round trip, rotation, wrong key.
3. `modules/notifications/domain/`: `enums.py`, `catalogue.py`, `quiet_hours.py`, `policy.py`, `dedupe.py`, `deeplinks.py`, `nudge.py`, `device_health.py`, `copy.py`. No Django imports. 100% covered.
4. `models.py` for the six W2.1 tables (ERD section 2), then `makemigrations`.
5. `services/settings.py`, `services/preferences.py`, `selectors/`, `serializers.py`, `views/settings.py`, `urls.py`.
6. `apps.py`: `ready()` registers the eraser and exporter in `core.registry` (this is the only wiring file).
7. `admin.py`: read-only views (no secret columns shown).

`config/settings.py` additions (next to the other env-driven values):

```python
# X-01 notifications
NOTIFICATIONS_ENABLED = env("NOTIFICATIONS_ENABLED", "false").lower() == "true"   # master kill switch, default off
NOTIFICATIONS_DISABLED_EVENTS = set(env_list("NOTIFICATIONS_DISABLED_EVENTS", ""))
NOTIFICATIONS_QUEUE = env("NOTIFICATIONS_QUEUE", "null")                           # null | qstash
NOTIFICATIONS_PUBLIC_BASE_URL = env("NOTIFICATIONS_PUBLIC_BASE_URL", "").rstrip("/")
VAPID_PRIVATE_KEY = env("VAPID_PRIVATE_KEY")
VAPID_SUBJECT = env("VAPID_SUBJECT")
QSTASH_TOKEN = env("QSTASH_TOKEN")
QSTASH_URL = env("QSTASH_URL")
QSTASH_CURRENT_SIGNING_KEY = env("QSTASH_CURRENT_SIGNING_KEY")
QSTASH_NEXT_SIGNING_KEY = env("QSTASH_NEXT_SIGNING_KEY")
CRON_SECRET = env("CRON_SECRET")
FIELD_ENCRYPTION_KEYS = env_list("FIELD_ENCRYPTION_KEYS", "")
FIELD_HASH_PEPPER = env("FIELD_HASH_PEPPER")
# In REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] add:
#   "notifications_write": "60/min", "notifications_test": "5/min", "notifications_read": "120/min",
```

Also add `"modules.notifications"` to `INSTALLED_APPS` and `path("api/v1/", include("modules.notifications.urls"))` to `config/urls.py`. Fail at start-up in production (`DEBUG` false) when `NOTIFICATIONS_ENABLED` is true but `FIELD_ENCRYPTION_KEYS` or `FIELD_HASH_PEPPER` is empty.

```bash
python manage.py makemigrations notifications -n initial
python manage.py makemigrations --check --dry-run          # must report no changes
python manage.py migrate
pytest modules/notifications core -q
ruff check . && ruff format .
```

**Check by hand** (get a token: sign in on the local web app, DevTools, Application, Local Storage, the `sb-...-auth-token` entry, copy `access_token`):

```bash
TOKEN='<access_token>'
curl -s localhost:8000/api/v1/notifications/settings/ -H "Authorization: Bearer $TOKEN" | python -m json.tool
curl -s -X PUT localhost:8000/api/v1/notifications/settings/ -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"timezone":"Asia/Kolkata","quiet_start":"23:00","quiet_end":"06:30"}' | python -m json.tool
curl -s localhost:8000/api/v1/notifications/categories/ -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

Expect 200s, a 400 for `"timezone":"Nowhere/Land"`, and a 403 `notifications_disabled` for every call when `NOTIFICATIONS_ENABLED=false`.

**Other tools:** deploy order above (production migrate, then merge). Nothing to configure in PostHog yet beyond the flags from section 1.

**Roll back:** nothing is user-visible. Leave `NOTIFICATIONS_ENABLED=false`.

### W2.2 Delivery (api)

Goal: register devices, send one real test push, store secrets safely.

```bash
cd "$ROOT" && git switch main && git pull --ff-only && git switch -c feat/x-01-w2-2-push-delivery
cd apps/api && source .venv/bin/activate
```

Build: `domain/push_hosts.py` (allow-list), `domain/devices.py` (label, key checks), `domain/payload.py` (payload v1), `channels/base.py` (`Channel` protocol, `SendResult`, `FakeChannel`) and `channels/__init__.py` (registry), `channels/webpush.py` (the only `pywebpush` import; `ttl`, `Urgency` header, 5 s timeout, maps 404 and 410 to `gone`, retries 429 and 5xx up to 3 attempts), `services/devices.py`, `services/notify.py` (`notify`, test push), `dispatch.py` (send and record, no scheduling yet), `views/devices.py`, `management/commands/send_test_push.py`, throttles. Tests use a fake HTTP layer; no test touches the network.

```bash
pytest modules/notifications -q && ruff check . && ruff format .
```

**Check with the spike subscription** (the `sub.json` from phase 1; the request shape is defined by `DeviceRegisterSerializer`; the device label is derived on the server, a `label` field is ignored; `NOTIFICATIONS_ENABLED=true`, the PostHog flags `notifications_ui` and `notifications_send`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` (a `mailto:` address), `FIELD_ENCRYPTION_KEYS` and `FIELD_HASH_PEPPER` must be set):

```bash
TOKEN='<access_token>'
curl -s -X POST localhost:8000/api/v1/notifications/devices/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"subscription\": $(cat ~/artha-push-spike/sub.json), \"platform\":\"macos\", \"browser\":\"chrome\", \"display_mode\":\"browser\", \"sw_version\":\"dev\"}"
curl -s localhost:8000/api/v1/notifications/devices/ -H "Authorization: Bearer $TOKEN" | python -m json.tool     # no endpoint or keys in the answer
curl -s -X POST localhost:8000/api/v1/notifications/devices/<device_id>/test/ -H "Authorization: Bearer $TOKEN"    # a real alert appears
python manage.py send_test_push --user <user_uuid> --device <device_id>                                           # same, from the shell
```

Then prove the failure path: delete the subscription in the browser (DevTools, Application, Service Workers, Unregister), send again, and confirm the device row shows `revoked_reason = gone`. A sixth test push in one minute returns 429.

**Other tools:** none. **Roll back:** leave the kill switch off.

### W2.3 Timer pipeline (api)

Goal: the timer-end push, end to end. This is the wave with the most risk, so keep it small and test-heavy.

```bash
cd "$ROOT" && git switch main && git pull --ff-only && git switch -c feat/x-01-w2-3-timer-pipeline
cd apps/api && source .venv/bin/activate
```

Build in this order (this is how it was built; every file has tests beside it):

1. **Announcer and judge in `focus`** (no migration: `ActiveTimer.version` already exists). `focus/events.py` holds one decorator, `announces`, applied to every public action in `focus/services.py` (`sync`, `start`, `pause`, `resume`, `extend`, `complete`, `skip_break`, `end`, `claim`, `change_context`, `delete_all_for_user`). After the action it compares the timer's (`client_id`, `version`) with what it was before and, if they differ, emits one `timer_changed` after commit (a rolled-back action and a no-op such as a heartbeat or a retried start emit nothing). The payload is small: `user_id`, `active`, `client_id`, `version`, `phase`, `ends_at`, `paused`, `overtime`, `round`, `minutes`, `subject_name`, `break_minutes`, `next_round`, `away_pending`, `at`. `update_settings` does not announce, because a running phase keeps the lengths and flags it started with. `focus/domain/judgement.py` is the pure rule and `focus.selectors.timer_end_judgement(user_id, client_id, expected_version, now)` is the read-only selector (one plain `SELECT`, never `sync` or `_settle`). `tests/test_announce.py` has a parametrised case per action and a guard that fails when a new public action is neither announcing nor listed as not moving the timer. The `tracking` announcers (`stopwatch_changed`, `goal_reached`) move to W3.2, where the alerts that use them are built.
2. **Queue port.** `scheduling/queue.py`: `DelayedQueue` (`publish(job_id, fire_at)`, `cancel(external_id)`), `NullQueue` (records calls, the default and the test double), `QStashQueue` (callback `NOTIFICATIONS_PUBLIC_BASE_URL` + `/api/v1/notifications/internal/jobs/{id}/fire/`, not-before time, 3 retries, deduplication id = job id, 3 s timeout on the publish) and the QStash signature verifier. It is the only file that imports `qstash`.
3. **Internal endpoints.** `scheduling/auth.py` and `views/internal.py`: `POST internal/jobs/{id}/fire/` needs a valid `Upstash-Signature` (current or next signing key, body hash and exact callback URL); `GET` and `POST internal/sweep/` need `Authorization: Bearer $CRON_SECRET`. Anything else is 401 with nothing done. No student login, no throttle, no UI flag; `CORS_URLS_REGEX` in `config/settings.py` keeps `internal/` out of CORS. The fire endpoint answers 200 for every outcome (sent, skipped, ignored) and 503 only when the work should be retried.
4. **Jobs.** `scheduling/jobs.py`: `plan_timer_end` (upsert on student, kind, timer, version; publish; a queue failure is logged and ignored), `cancel_for_timer`, and `fire_job` (atomic claim `pending` to `fired`, then kill switches, then the handler's judgement, then `notify`). `handlers.py` maps a job kind to its event key and read-only judgement; `subscribers.py` turns `timer_changed` into plan or cancel and is registered in `apps.py`. Skip reasons recorded on the job: `changed`, `paused`, `gone`, `flag_off`, `disabled`, `stale`.
5. **Sweep.** `scheduling/sweep.py`: fires pending jobs that are more than 10 seconds overdue, oldest first, at most 200 jobs and 20 seconds per run, and logs `sweep_run`. It is a list of steps (`STEPS`), so nudges, digests and pruning are added later as further steps.
6. **Click.** `services/inbox.py` and `views/inbox.py`: `POST /api/v1/notifications/inbox/{id}/click/` marks the student's own notification read and its sent pushes clicked; 204, idempotent, 404 for anyone else's; same UI gate and `notifications_write` budget as the other student endpoints.

```bash
pytest modules/focus modules/tracking modules/notifications -q     # existing focus and tracking tests must still pass
ruff check . && ruff format .
```

Two tests (`test_job_claim_postgres.py`) need real concurrent connections and the query planner, so they run on Postgres only: locally they are skipped on SQLite and CI runs them. To run them yourself, point `DATABASE_URL` at a local Postgres 15 or later.

**Settings the internal endpoints need at runtime:** `NOTIFICATIONS_PUBLIC_BASE_URL`, `QSTASH_CURRENT_SIGNING_KEY` and `QSTASH_NEXT_SIGNING_KEY` for `fire` (without both keys every call is refused, on purpose), `CRON_SECRET` for `sweep`, and for publishing `NOTIFICATIONS_QUEUE=qstash` with `QSTASH_TOKEN` (and `QSTASH_URL` for a non-default region). Planning also needs `NOTIFICATIONS_ENABLED=true` and the PostHog flag `notifications_send` on for the student.

**Check locally without the queue** (`NOTIFICATIONS_QUEUE=null`): start a 5-minute round in the app with a registered device, wait for the end, then run the sweep by hand (the sweep waits 10 seconds after the end before it steps in). It fires overdue jobs:

```bash
curl -s -X POST localhost:8000/api/v1/notifications/internal/sweep/ -H "Authorization: Bearer $CRON_SECRET"   # {"fired":1,...}
curl -s localhost:8000/api/v1/notifications/internal/sweep/ -H "Authorization: Bearer $CRON_SECRET"            # GET works too (Vercel cron)
curl -s -X POST localhost:8000/api/v1/notifications/internal/sweep/                                           # expect 401
```

**Check the click endpoint** (take a notification id from the push URL `?n=<id>`, or `select id from notifications_notification order by created_at desc limit 1;`):

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST localhost:8000/api/v1/notifications/inbox/<notification_id>/click/ -H "Authorization: Bearer $TOKEN"   # 204, twice
```

**Check with the real queue** (needs a public URL for QStash to call):

```bash
cloudflared tunnel --url http://localhost:8000          # terminal 1, note https://<random>.trycloudflare.com
# terminal 2, in apps/api with the venv active:
export NOTIFICATIONS_QUEUE=qstash
export NOTIFICATIONS_PUBLIC_BASE_URL=https://<random>.trycloudflare.com
export DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,<random>.trycloudflare.com
export QSTASH_TOKEN=... QSTASH_CURRENT_SIGNING_KEY=... QSTASH_NEXT_SIGNING_KEY=...
python manage.py runserver 8000
```

Run these four cases and read the `job_fired`, `job_skipped` and `job_cancelled` log lines in the terminal; the job table shows what happened to each version:

```sql
select status, skip_reason, expected_version, fire_at, fired_at, attempts from notifications_scheduledjob order by created_at desc limit 8;
```

1. Start a 5-minute round, leave it: alert at 5:00 (lateness under 5 s), job `fired`.
2. Start, pause at 4:59: nothing arrives; the job is `cancelled` and the QStash log shows the message deleted. (`job_skipped` with reason `changed` appears only if the cancel call itself failed.)
3. Start, press +5 minutes: one alert, at the new end; the first job is `cancelled`.
4. Start, stop the API for the end time, start it again within a minute and run the sweep: the alert arrives late but once (QStash may also retry; the second call finds the job already claimed and does nothing).

Also confirm in the Upstash console (QStash, Logs) that the delivery to your tunnel shows 200.

**Other tools:** QStash console only for the logs. **Roll back:** `NOTIFICATIONS_ENABLED=false` (next deployment) or the PostHog flag at 0% (within about a minute); messages already queued then arrive and are recorded `skipped: disabled` or `skipped: flag_off`.

### W2.4 Web foundation

Goal: service worker, manifest, settings screen, device list, test button.

**As built (this wave is implemented).** Everything below under "Create" exists already; run the checks and the manual steps instead of re-creating files.

- `apps/web/src/sw/` holds the worker (`sw.ts`) and its pure, tested parts: `payload.ts` (payload v1; an unknown version or bad JSON still shows one generic alert), `deeplink.ts` (the allow-list, mirrored from `apps/api/modules/notifications/domain/deeplinks.py`; `deeplink.test.ts` reads that file and fails when they drift), `handlers.ts` (push, click, `pushsubscriptionchange`), `applicationServerKey.ts`, `messages.ts`. There is no `fetch` handler and no Cache API use (a test checks the bundle).
- `scripts/build-sw.mjs` compiles it to `public/sw.js` (generated, git-ignored, excluded from ESLint and Prettier). `pnpm dev` and `pnpm build` run it first. The worker version is the first 7 characters of `VERCEL_GIT_COMMIT_SHA` (else `dev`); the same id is sent as `sw_version` when a device registers.
- `src/modules/notifications/` follows the module layout (components, containers, hooks, lib, barrel). Route `/app/settings/notifications` is gated by the PostHog flag `notifications_ui` (web, fails open) and by the API's 403 `notifications_disabled`. The link sits in the Settings menu (`modules/layout/workspace-nav.ts`).
- `NotificationsBoot` (root layout) registers `/sw.js` after load in production builds, or in `pnpm dev` when `VITE_SW_DEV=true`. `NotificationsAppEffects` (`/app` layout) handles `?n=<id>` (one `POST inbox/{id}/click/`, then the parameter is removed) and refreshes this browser's registration at most every 12 hours, or at once when the worker re-subscribes.
- Icons: `pnpm --filter @artha/web og` now also writes `public/icon-192.png` and `public/icon-maskable-512.png` from the same brand mark as `icon-512.png`.
- Limits mirrored from the API live in `modules/notifications/lib/limits.ts` (`limits.test.ts` reads `apps/api/config/settings.py`).
- Env: `VITE_VAPID_PUBLIC_KEY` (section 1) and the optional `VITE_SW_DEV` are declared in `src/lib/env.ts` and `.env.example`.

```bash
cd "$ROOT" && git switch main && git pull --ff-only && git switch -c feat/x-01-w2-4-web-push-foundation
pnpm --filter @artha/web add -D esbuild            # compiles the service worker (PRD Q5)
```

Create (all under `apps/web`):

1. `src/sw/payload.ts`, `src/sw/handlers.ts`, `src/sw/sw.ts`, with `*.test.ts` next to them (push parsing, show with `tag`, click routing, deep-link allow-list, `pushsubscriptionchange`).
2. `scripts/build-sw.mjs`:

```js
import { build } from 'esbuild'

await build({
  entryPoints: ['src/sw/sw.ts'],
  outfile: 'public/sw.js',
  bundle: true,
  minify: true,
  format: 'iife',
  target: 'es2020',
  define: { __SW_VERSION__: JSON.stringify((process.env.VERCEL_GIT_COMMIT_SHA ?? 'dev').slice(0, 7)) },
})
```

3. `package.json` scripts in `apps/web`: `"build:sw": "node scripts/build-sw.mjs"`, and change `"dev"` to `"node scripts/build-sw.mjs && vite dev"` and `"build"` to `"node scripts/build-sw.mjs && vite build"`. Add `apps/web/public/sw.js` to `.gitignore` (generated).
4. Icons and manifest. Done by `pnpm --filter @artha/web og` (icons) and `public/manifest.webmanifest` (`id`, `scope`, 192, 512 and maskable icons, a Start focus shortcut). The maskable icon is the same mark on a full-bleed square; have the designer confirm the safe zone and replace the three PNGs with final art when it exists (keep the file names).
5. `apps/web/vercel.json`: add

```json
"headers": [
  { "source": "/sw.js", "headers": [
    { "key": "Cache-Control", "value": "no-cache, no-store, must-revalidate" },
    { "key": "Service-Worker-Allowed", "value": "/" }
  ] }
]
```

6. `src/modules/notifications/` (components, containers, hooks, lib, `index.ts`) and the route file `src/routes/app.settings.notifications.tsx` (same pattern as `app.settings.focus.tsx`, `noindex: true`). Register the worker only in production builds, or when `VITE_SW_DEV=true`.

```bash
pnpm --filter @artha/web exec vitest run src/modules/notifications src/sw
pnpm typecheck && pnpm lint:fix && pnpm format
pnpm build:web && pnpm --filter @artha/web start           # production build on http://localhost:3000
```

**Check in Chrome** on `http://localhost:3000/app/settings/notifications`: DevTools, Application, Manifest (no installability warnings), Service Workers (status running), then Subscribe, Send me a test, and the alert appears with the tab closed. Repeat the visual check in all four themes and at 320, 768 and 1280 px, keyboard only.

**Other tools:** Vercel web project must have `VITE_VAPID_PUBLIC_KEY` (section 1) and be redeployed after it is added. The API must have `NOTIFICATIONS_ENABLED=true` and the device endpoints from W2.2 deployed for the device list and test button to work; `POST inbox/{id}/click/` arrives with W2.3, so deploy W2.3 first or `?n=` is a silent no-op. **Roll back:** flag `notifications_ui` at 0% hides the screen and the Settings link (the worker stays registered; it caches nothing and only shows pushes).

### W2.5 Permission step (web and api)

Goal: the onboarding step `alerts` and one alert per timer end. The follow-up ask after a "Not now" and after the first finished round (PRD 5.1, last paragraph) is **not** in this wave: it needs the focus round-end signal and the ask-count rule together, so it is tracked as W2.5b.

```bash
cd "$ROOT" && git switch main && git pull --ff-only && git switch -c feat/x-01-w2-5-alerts-step
```

**What changed**

- API: `profiles/onboarding_steps.py` registers `alerts` through the existing registry (`since = 3`, optional, order 80). It is available only while `notifications.selectors.ui_enabled` is true (environment switch plus the `notifications_ui` flag) and is done when `notifications.selectors.permission_decided` is true (facts over flags). Saving it is refused (400) until a decision exists. `ONBOARDING_VERSION` is now **3**, because a step applies only once the version reaches its `since`. No table, no migration.
- Web: `notifications` module gains `AlertsStepContainer`, the cards (`AlertsPreCard`, `InstallGuide`, `UnblockSteps`, `InAppBrowserCard`, `AlertsOutcomeCard`), `lib/alertsStep.ts` (every branch of PRD 5.1 as pure functions), `lib/clipboard.ts` and `lib/alertTag.ts`. `personalization` renders it as `AlertsStep` (`?step=alerts`) and saves the onboarding step once the decision is recorded.
- Every outcome is recorded with `POST permission-state` (source `onboarding`) before the step finishes, so a failed record never moves the student on without one. The device is registered on Allow (same `enableAlerts` flow as Settings). "Send me a test" is on the granted card.
- Shared tag: `useFocusAlerts` gives the local browser notification the tag `timer:<client_id>`, the one the push carries (`notifications/domain/copy.py`), so a device that gets both shows one alert. A visible tab shows no system notification of its own, so the push is then the only one. `local_alert_shown` is sent with the tag.
- Events: `alerts_step_viewed`, `alerts_step_completed` (`result`: granted, denied, dismissed, skipped_install, blocked, unsupported), plus the existing `push_permission_*` and `push_test_requested`.
- Returning students: a student who completed an earlier version is not walked through it (optional steps never re-prompt). The "Finish your setup" card on `/app` offers it once (`workspace/lib/setupCards.ts`), and the link now works for returning students (`walkOf` accepts the step named in the URL). A returning student with nothing new to answer finishes quietly, without the celebration.

**Configure:** nothing new. It needs the W2.1 to W2.4 settings: `NOTIFICATIONS_ENABLED=true`, `VITE_VAPID_PUBLIC_KEY`, the PostHog flag `notifications_ui` (fails open on the web, and the API step also needs the environment switch).

**Roll back:** PostHog `notifications_ui` to 0% hides the step on the web and the API reports it unavailable within about a minute; `NOTIFICATIONS_ENABLED=false` hides it from the next deployment. Neither touches the rest of onboarding. Reverting the version bump is not needed.

```bash
cd apps/api && source .venv/bin/activate && pytest modules/profiles modules/notifications -q && ruff check . && ruff format --check . && cd "$ROOT"
pnpm --filter @artha/web exec vitest run src/modules/notifications src/modules/personalization src/modules/workspace src/modules/focus
pnpm check
```

**Check every branch of PRD 5.1** with `NOTIFICATIONS_ENABLED=true`, `VITE_VAPID_PUBLIC_KEY` set and a fresh account (open `/app/onboarding?step=alerts` to jump to the step; the other steps must be done first):

1. Desktop Chrome, permission "Ask": pre-prompt, Turn on alerts, Allow, "Alerts are on", Send me a test, Continue. Repeat with Block (denied card), with the prompt closed (dismissed card, "Turn on alerts after all"), and with Not now.
2. Desktop Chrome, blocked (`chrome://settings/content/notifications`, add the site to Block, reload): unblock steps, change the setting to Allow, press Check again (screen moves to "One more tap to finish"). Also Skip for now.
3. Real iPhone, Safari tab: Home Screen guide, Continue without alerts. Then add to Home Screen, open the icon, go to the step: pre-prompt and push.
4. WhatsApp or Instagram in-app browser (send yourself the link): Open Artha in your browser, Copy link, Continue without alerts.
5. A browser without push (for example a Firefox private window with notifications off, or an old iOS): the unsupported note.
6. Keyboard only on each screen (Tab order, Enter, focus lands on the card heading when a screen changes), a screen reader (the polite region speaks outcomes), reduced motion on (no tick animation), the four themes, 320 px width.
7. One alert only: start a round, switch to another tab, let it end. One notification appears, not two.

**Other tools:** PostHog, create an insight for `alerts_step_completed` broken down by `result`.

### W2.6 Keep awake (independent, can run in parallel)

```bash
cd "$ROOT" && git switch main && git pull --ff-only && git switch -c feat/x-01-w2-6-keep-awake
cd apps/api && source .venv/bin/activate
# add keep_awake and keep_awake_in_breaks to FocusSettings (models, serializer, selectors.settings_dict), then:
python manage.py makemigrations focus -n keep_awake
pytest modules/focus -q && cd "$ROOT"
```

Web: `useWakeLock` (request on start and resume, release on pause, end and phase end, re-request on `visibilitychange`, 4-hour cap), status chip, two switches in `/app/settings/focus`, a CI test that fails if a `Permissions-Policy` header disables `screen-wake-lock` or `notifications` on `/app/*`.

```bash
pnpm --filter @artha/web exec vitest run src/modules/focus && pnpm check
curl -sI https://<your-web-domain>/app | grep -i permissions-policy       # after deploy; must not list screen-wake-lock
```

Check on a real Android phone and an iPhone Home Screen app with a 10-minute screen timeout (PRD FR-K10). Production migration first (deploy order above). Roll back: flag `keep_awake` at 0%.

### W2.7 Launch hardening

Goal: be able to see problems before students do, then run the device matrix.

```bash
cd "$ROOT" && git switch main && git pull --ff-only && git switch -c feat/x-01-w2-7-hardening
cd apps/api && source .venv/bin/activate
python manage.py prune_notifications --dry-run             # prints counts per table, deletes nothing
pytest modules/notifications -q
```

**Supabase: the per-minute sweeper** (works on any Vercel plan; Supabase dashboard, Database, Extensions: enable `pg_cron` and `pg_net` if `create extension` is refused). In the SQL editor:

```sql
create extension if not exists pg_cron;
create extension if not exists pg_net;

select vault.create_secret('https://api.<your-domain>/api/v1/notifications/internal/sweep/', 'artha_sweep_url');
select vault.create_secret('<CRON_SECRET value>', 'artha_cron_secret');

select cron.schedule(
  'artha-notifications-sweep',
  '* * * * *',
  $$
  select net.http_post(
    url := (select decrypted_secret from vault.decrypted_secrets where name = 'artha_sweep_url'),
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer ' || (select decrypted_secret from vault.decrypted_secrets where name = 'artha_cron_secret')
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 25000
  );
  $$
);
```

Check after two minutes: `select status, return_message, start_time from cron.job_run_details order by start_time desc limit 5;` and `select status_code, created from net._http_response order by created desc limit 5;` (expect 200). Stop it any time with `select cron.unschedule('artha-notifications-sweep');`.

**Alternative on Vercel Pro:** add to `apps/api/vercel.json` `"crons": [{ "path": "/api/v1/notifications/internal/sweep/", "schedule": "* * * * *" }]`. Vercel sends `Authorization: Bearer <CRON_SECRET>` when the `CRON_SECRET` variable exists on the project. Run only one of the two sweepers.

**Watch the targets.** Saved SQL in the Supabase editor (run daily during rollout):

```sql
select count(*) as sent_or_failed,
       round(avg((status = 'sent')::int)::numeric, 4) as accepted_ratio,
       percentile_cont(0.95) within group (order by lateness_ms) filter (where status = 'sent') as p95_ms
from notifications_delivery
where channel = 'push' and attempted_at > now() - interval '1 day' and status in ('sent', 'failed');
```

Targets: `accepted_ratio >= 0.98`, `p95_ms <= 5000`. The sweep also runs the same check over the last 15 minutes and logs an error (`push_slo_breach`) when it fails; in **Sentry** create an alert rule on that message for the `artha-api` project, notify you by email. In **PostHog** build one dashboard from `alerts_step_completed`, `push_permission_result`, `push_clicked`, `notification_pref_changed`.

**Device matrix** (sign off in `docs/X-01-spike-results.md` under a new heading): Android Chrome, iPhone Safari tab (install guide), iPhone Home Screen app, desktop Chrome, Edge, Firefox, Safari. Each: allow, test push, timer-end push with the tab closed, pause cancels, blocked flow, remove device.

Commit, production migrate if any, merge, deploy. Gate G1 is met when the matrix is signed off and the SQL above meets both targets on your own devices over two days.

## 4. Launching phase 2: staged rollout and rollback

Do this only after gate G1 (W2.7 signed off). Everything is deployed with `NOTIFICATIONS_ENABLED=false` and the flags at 0%, so no student has seen anything yet.

1. **Confirm production is current.** All migrations applied (deploy order in section 3), API and web deployed from `main`, the sweeper from W2.7 shows `200` in `net._http_response`.
2. **Turn the master switch on** (it is read at start-up, so it needs a redeploy):

```bash
cd "$ROOT/apps/api"
npx vercel env rm NOTIFICATIONS_ENABLED production --yes
printf '%s' 'true' | npx vercel env add NOTIFICATIONS_ENABLED production
npx vercel ls --prod | head -5            # note the newest production deployment URL
npx vercel redeploy <deployment-url>      # or: Vercel dashboard, Deployments, the three dots, Redeploy
```

3. **Climb the ladder in PostHog** (Feature flags, `push_notifications`, then `keep_awake`). After each step wait the hold time, then check the three things below. Move up only if all are fine.

| Step | Audience | Hold |
| --- | --- | --- |
| 1 | Team, by email in the release condition | 1 day |
| 2 | 5% of students | 3 days |
| 3 | 25% of students | 3 days |
| 4 | 100% | stay on watch for a week |

   Checks at each step: the Supabase SQL from W2.7 (`accepted_ratio >= 0.98`, `p95_ms <= 5000`), no `push_slo_breach` alert in Sentry, and in PostHog the `notification_pref_changed` rate (below 20%) and `alerts_step_completed` result mix.

4. **Roll back, fastest first.**

| Need | Do | Takes effect |
| --- | --- | --- |
| Pause for everyone | PostHog flag `push_notifications` to 0% | about 1 minute (flag cache) |
| Stop one event type | `printf '%s' 'daily_nudge' \| npx vercel env add NOTIFICATIONS_DISABLED_EVENTS production` (remove the old value first), redeploy | next deployment |
| Hard stop | Set `NOTIFICATIONS_ENABLED` to `false`, redeploy | next deployment |
| Stop the sweeper | `select cron.unschedule('artha-notifications-sweep');` in Supabase | immediately |

Nothing needs a database rollback: queued messages that arrive later find sending off and are recorded as skipped.

## 5. Phase 3: more alerts (about 4 to 5 weeks)

Every wave starts and ends as in section 0, and uses the deploy order in section 3. Pure-logic tests first, one commit per concern.

### W3.1 Inbox and bell

No migration: the bell polls, so no student-facing database policy and no Realtime exposure are needed (the Data API stays disabled as in `docs/SETUP.md` 2.4).

```bash
cd "$ROOT" && git switch main && git pull --ff-only && git switch -c feat/x-01-w3-1-inbox
cd apps/api && source .venv/bin/activate && pytest modules/notifications -q && cd "$ROOT"
pnpm --filter @artha/web exec vitest run src/modules/notifications && pnpm check
```

API: `services/inbox.py`, `selectors/inbox.py`, `views/inbox.py` (list with cursor, unread count, mark read). Web: `BellContainer` (React Query with `refetchInterval` 60 seconds, refetch on window focus, and an immediate refetch when the service worker posts a message after a push), `InboxContainer` at `/app/notifications`, `InboxList`. Check: send a test push, the bell count rises within a minute (at once if the tab is open); open the inbox, mark read; four themes and 320 to 1280 px.

### W3.2 Tracker alerts and deferred delivery

```bash
git switch -c feat/x-01-w3-2-tracker-alerts      # after syncing main
cd apps/api && source .venv/bin/activate && pytest modules/tracking modules/notifications -q
```

Build: `tracking` announcers for stopwatch and goal, handlers `stopwatch_long`, `goal_reached`, `streak_at_risk`, and the `deliver_deferred` job. Check quiet hours: set quiet hours around the current time (`PUT settings/` as in W2.1), reach the daily goal, and confirm the push is held:

```sql
select kind, status, fire_at from notifications_scheduledjob where kind = 'deliver_deferred' order by created_at desc limit 5;
```

It must fire at the end of the window (or be dropped after `expires_at`). Confirm a goal alert comes once a day and the streak alert is skipped when the goal is met.

### W3.3 Daily thought and nudge

```bash
git switch -c feat/x-01-w3-3-thought-nudge
cd apps/api && source .venv/bin/activate
python manage.py makemigrations notifications -n motivation
python manage.py migrate
python manage.py load_motivation_seed              # loads drafts only; safe to run twice
pytest modules/notifications -q
```

Production: migrate first, merge, then `python manage.py load_motivation_seed` against production the same way as the migration (section 3 environment), then an editor opens `https://api.<your-domain>/<DJANGO_ADMIN_PATH>/`, Notifications, Messages, reviews the drafts and publishes them. Nothing is sent from a draft.

Check: first open of the day shows one thought card; reload shows the same one. For the nudge, in the SQL editor `update notifications_settings set next_nudge_at = now() where user_id = '<your uuid>';`, then run the sweep (section 3, W2.3 curl). A student who opened the app today gets no push (`push_suppressed`, reason `visited_today`); one who did not, gets exactly one. Change the time zone in settings and confirm `next_nudge_at` moves.

### W3.4 Revision, exam countdown, content

```bash
git switch -c feat/x-01-w3-4-more-providers
cd apps/api && source .venv/bin/activate && pytest modules/notifications modules/coverage -q
```

Check with your account: set the exam date in coverage settings to 30 days ahead, wait for or force the morning run (as above), and confirm one milestone push; with chapters due for revision, one revision push that day, never two.

### W3.5 Weekly email

Django needs outgoing email (the existing SMTP is only inside Supabase Auth). Use the provider already set up in `docs/SETUP.md` 2.3.1; SPF, DKIM and DMARC are already in place.

```bash
git switch -c feat/x-01-w3-5-weekly-email
cd apps/api && source .venv/bin/activate
export EMAIL_HOST=smtp.resend.com EMAIL_PORT=587 EMAIL_HOST_USER=resend EMAIL_USE_TLS=true
export EMAIL_HOST_PASSWORD='<provider api key>' DEFAULT_FROM_EMAIL='ArthaCommerce <no-reply@mail.<your-domain>>'
python manage.py sendtestemail you@example.com                  # Django built-in; must land in the inbox, not spam
python manage.py send_test_push --channel email --user <your uuid>
pytest modules/notifications -q
```

Add the same six variables to the Vercel API project (`npx vercel env add ...` as in section 1; the password is a secret). Check the unsubscribe link and the `List-Unsubscribe` header in the received message, and that a student with email switched off gets none.

### W3.6 Android notification buttons

```bash
cd "$ROOT" && git switch main && git pull --ff-only && git switch -c feat/x-01-w3-6-action-buttons
cd apps/api && source .venv/bin/activate
python manage.py makemigrations notifications -n actiontoken && python manage.py migrate
pytest modules/notifications -q
```

Check on a real Android phone: the timer-end alert shows Start break and +5 min; tapping one changes the timer without opening the app. Replay the same token:

```bash
curl -s -X POST https://api.<your-domain>/api/v1/notifications/actions/ -H 'Content-Type: application/json' -d '{"token":"<token from the payload>"}'
# the second call must be rejected
```

### W3.7 Fatigue controls

```bash
git switch -c feat/x-01-w3-7-fatigue
cd apps/api && source .venv/bin/activate && pytest modules/notifications -q && cd "$ROOT"
pnpm --filter @artha/web exec vitest run src/modules/notifications && pnpm check
```

Unit tests cover "five consecutive unclicked pushes over at least three days" and "offered once per 30 days". Gate G3 (PRD 13.2) is checked with the SQL from W2.7 plus this cap check, which must return no rows:

```sql
select user_id, date_trunc('day', attempted_at at time zone 'Asia/Kolkata') as day, count(*)
from notifications_delivery
where status = 'sent' and counts_toward_cap and attempted_at > now() - interval '7 days'
group by 1, 2 having count(*) > 4;     -- cap is 3, plus one reserved slot for priority 1
```

Roll out each P3 wave through the same flag ladder as section 4 (steps 2 to 4 are enough: 5%, 25%, 100%).

## 6. Phase 4: floating timer (about 2 weeks, flag `floating_timer`)

Scope is the approved PRD B (pop-out, install prompt, `/app/focus/mini`). Web only, plus one small migration for three settings columns.

```bash
cd "$ROOT" && git switch main && git pull --ff-only && git switch -c feat/x-01-p4-floating-timer
cd apps/api && source .venv/bin/activate
python manage.py makemigrations focus -n popout           # popout_on_start, popout_size, popout_prompt_seen
pytest modules/focus -q && cd "$ROOT"
pnpm --filter @artha/web exec vitest run src/modules/focus && pnpm check
pnpm build:web && pnpm --filter @artha/web start
```

Build: `useDocumentPip`, `PopOutTimer` (reuses `MiniTimerView`, copies design tokens and the theme into the pop-out document), `/app/focus/mini` fallback route (`noindex`, 320 px wide), the settings in `/app/settings/focus`, the install prompt (`beforeinstallprompt`, once per 30 days, after the second finished round), an iPhone install guide. Production migration first, then merge.

Check: Chrome and Edge 116 or newer, Firefox 151 or newer: click Pop out, switch to another app, pause from the pop-out and see the main tab follow within one second; round end shows the large next-step button. All four themes inside the pop-out at pill size (contrast check). Safari and older Firefox: the fallback window. Real Android: the notification buttons from W3.6. PostHog: insight on `popout_opened` for desktop focus students (this is the input to gate G4).

## 7. Phase 5: desktop companion (only if gate G4 passes)

Gate G4 (approved PRD): four weeks after P4, at least 25% of desktop focus students use the pop-out or the installed app, and feedback asks for "works when my browser is closed" or system-wide keep awake. If not met, stop here.

Before any code, write a build document like this one for the companion (new package `apps/desktop`, CI job, signing, release and update process), and have it approved. Setup commands when you start:

```bash
# once, on macOS
xcode-select --install
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh && source "$HOME/.cargo/env"

cd "$ROOT/apps"
pnpm create tauri-app desktop --template react-ts --manager pnpm --identifier <reverse.domain.artha>   # run with --help first if flags have changed
cd desktop && pnpm install
pnpm tauri dev                                    # run the app
pnpm tauri build                                  # unsigned local build

pnpm tauri signer generate -w ~/.tauri/artha-updater.key       # key pair for signed auto-update; keep the private key out of the repo
```

Other tools and costs to arrange first: Apple Developer Program membership (Developer ID certificate and notarization: `APPLE_CERTIFICATE`, `APPLE_CERTIFICATE_PASSWORD`, `APPLE_SIGNING_IDENTITY`, `APPLE_ID`, `APPLE_PASSWORD` (an app-specific password), `APPLE_TEAM_ID` as CI secrets), a Windows code-signing certificate, and a place to host installers and the update manifest. The app registers itself through `POST devices/` with `kind = desktop_app` (already supported by the schema), signs in with the system browser (PKCE) and keeps the refresh token in the OS keychain. Flag: `desktop_companion`. Keep-awake across apps is added here with a Tauri-side wake lock (choose the plugin in the P5 document).

## 8. Environment variables added by X-01 (merge into `docs/SETUP.md` section 10)

| Variable | Web | API | Secret | Phase |
| --- | --- | --- | --- | --- |
| `VITE_VAPID_PUBLIC_KEY` | yes | | no (public by design) | P2 |
| `VITE_SW_DEV` | yes (local only) | | no | P2 |
| `VAPID_PRIVATE_KEY` | | yes | yes | P2 |
| `VAPID_SUBJECT` | | yes | no | P2 |
| `FIELD_ENCRYPTION_KEYS`, `FIELD_HASH_PEPPER` | | yes | yes | P2 |
| `CRON_SECRET` | | yes (and Supabase vault) | yes | P2 |
| `QSTASH_TOKEN`, `QSTASH_CURRENT_SIGNING_KEY`, `QSTASH_NEXT_SIGNING_KEY` | | yes | yes | P2 |
| `QSTASH_URL` | | yes (only if the region needs it) | no | P2 |
| `NOTIFICATIONS_ENABLED`, `NOTIFICATIONS_QUEUE`, `NOTIFICATIONS_PUBLIC_BASE_URL`, `NOTIFICATIONS_DISABLED_EVENTS` | | yes | no | P2 |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | | yes | no | P3 |
| `EMAIL_HOST_PASSWORD` | | yes | yes | P3 |

Rule from `SETUP.md` stays: nothing secret gets a `VITE_` prefix.

## 9. Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| `fire` returns 503 | A transient failure after the job was claimed (database or push adapter). The job went back to `pending` and the queue retries; after 3 attempts it is `failed`. Read the traceback logged just before |
| `fire` returns 401 | Signature check failed. `NOTIFICATIONS_PUBLIC_BASE_URL` must equal the exact origin QStash calls (scheme and host, no trailing slash); the signing keys must match the QStash project; both signing keys must be set (with either missing every call is refused); the check uses the raw body |
| `fire` returns 400 or 403 `Invalid host header` | The tunnel or domain is missing from `DJANGO_ALLOWED_HOSTS` |
| Nothing is ever sent | `NOTIFICATIONS_ENABLED` is false, the PostHog flag is not true for your user (sending is strict), or no active device. `push_suppressed` logs say which |
| Alert arrives late | The queue call failed at start and the sweep sent it. Look for `sweep_run` with `fired > 0`; check the QStash logs and the sweeper (`cron.job_run_details`) |
| Two alerts for one round end | A local alert without the shared `tag`, or two devices on the same browser profile. Check `tag` in the payload and in `useFocusAlerts` |
| Device disappears after one send | Push service answered 404 or 410: the subscription was unregistered or the permission was blocked. Expected; resubscribe |
| iPhone shows no permission prompt | The site is not installed to the Home Screen, or the prompt was not triggered by a tap |
| `pywebpush` raises a key error | Wrong private key format. Re-run the phase 1 `send.py` check with the same key |
| New service worker does not take over | `/sw.js` is cached. Confirm the `Cache-Control` header from `vercel.json`; in DevTools use Update on reload once |
| CI fails on a policy that uses `auth.uid()` | CI uses plain Postgres. Wrap any such SQL in the `pg_namespace` check (ERD section 7) |
| `makemigrations --check` reports changes | A model changed without a migration, or `nulls_distinct=False` was dropped from the delivery unique constraint |
| Vercel cron refused at deploy | Hobby plan allows daily crons only; use the Supabase sweeper (W2.7) |
