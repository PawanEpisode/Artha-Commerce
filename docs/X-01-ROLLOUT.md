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

Goal: the onboarding step `alerts`, the follow-up ask after "Not now", and one alert per timer end.

```bash
cd "$ROOT" && git switch main && git pull --ff-only && git switch -c feat/x-01-w2-5-alerts-step
```

**What changed**

- API: `profiles/onboarding_steps.py` registers `alerts` through the existing registry (`since = 3`, optional, order 80). It is available only while `notifications.selectors.ui_enabled` is true (environment switch plus the `notifications_ui` flag) and is done when `notifications.selectors.permission_decided` is true (facts over flags). Saving it is refused (400) until a decision exists. `ONBOARDING_VERSION` is now **3**, because a step applies only once the version reaches its `since`. No table, no migration.
- Web: `notifications` module gains `AlertsStepContainer`, the cards (`AlertsPreCard`, `InstallGuide`, `UnblockSteps`, `InAppBrowserCard`, `AlertsOutcomeCard`), `lib/alertsStep.ts` (every branch of PRD 5.1 as pure functions), `lib/clipboard.ts` and `lib/alertTag.ts`. `personalization` renders it as `AlertsStep` (`?step=alerts`) and saves the onboarding step once the decision is recorded.
- Every outcome is recorded with `POST permission-state` (source `onboarding`) before the step finishes, so a failed record never moves the student on without one. The device is registered on Allow (same `enableAlerts` flow as Settings). "Send me a test" is on the granted card.
- Shared tag: `useFocusAlerts` gives the local browser notification the tag `timer:<client_id>`, the one the push carries (`notifications/domain/copy.py`), so a device that gets both shows one alert. A visible tab shows no system notification of its own, so the push is then the only one. `local_alert_shown` is sent with the tag.
- Events: `alerts_step_viewed`, `alerts_step_completed` (`result`: granted, denied, dismissed, skipped_install, blocked, unsupported), plus the existing `push_permission_*` and `push_test_requested`.
- Follow-up ask (PRD 5.1, last paragraph): a student who chose "Not now" (state `dismissed`) is asked again at most twice more, at least 14 days apart, and only right after a focus round ends on `/app/focus`. The rule is pure (`notifications/domain/followup.py`) and the server owns it: `GET settings/` now returns `followup_due`, and `POST permission-state/` with `pre_prompt_shown` from source `followup` counts an ask only when one is due (a reload counts nothing) and never changes a stored decision, so the onboarding step and setup card stay done. The page (`FollowUpAskContainer`, mounted in the focus page) shows an inline card, never a modal; Turn on alerts runs the same enable flow with source `followup`, Not now records `dismissed`. A block, an unsupported browser, a missing iPhone install or an in-app browser is never nagged. Needs no new setting.
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
7. Follow-up ask: with a fresh account choose Not now on the step; in the Django shell move that row 15 days back (`NotificationSettings.objects.filter(user_id=...).update(last_asked_at=..., permission_decided_at=...)`), open `/app/focus`, run a short round to its end: the card appears below the timer. Reload: it does not come back (the ask was counted). Repeat twice more: after the third ask in all, never again. A student with alerts blocked never sees it.
8. One alert only: start a round, switch to another tab, let it end. One notification appears, not two.

**Other tools:** PostHog, create an insight for `alerts_step_completed` broken down by `result`.

### W2.6 Keep awake (independent, can run in parallel)

**What changed**

- API: `focus_focussettings` gains `keep_awake` (default true) and `keep_awake_in_breaks` (default false), migration `focus.0003_keep_awake` (two columns with defaults, so it is safe on a live table). Both are in the settings serializer, the `PUT /focus/settings/` writer and `settings_dict`, so the choice follows the student across devices. The pop-out columns wait for P4.
- Web: the `keepawake` module (below), two switches under a new "Screen" heading in `/app/settings/focus` (`focus` module), and the chip wired into `FocusPageContainer` and `TrackerContainer`.
- The hook requests a screen lock when a focus round is **running** (a break only if "also during breaks" is on), and releases it on pause, end, skip, phase end and when the timer is claimed as away. The browser drops the lock whenever the tab is hidden, so the hook asks again on `visibilitychange`. A refusal (low battery, battery saver) is not an error and shows no toast: the chip says "Screen may sleep" and nothing else changes. One hold lasts at most four hours, then it is released and not asked for again until the timer is paused and resumed.
- The chip ("Screen stays on" / "Screen may sleep") lives in a polite live region, uses an icon and words (never colour alone), and is hidden when the browser has no Wake Lock API. The settings page says so on such a browser but keeps the switches, because the setting is the student's, not the browser's.
- Gate: PostHog flag `keep_awake` (fails open on the web, like `notifications_ui`). At 0% the screen lock is never requested, the chip is hidden and the "Screen" section disappears. The timer never depends on the lock.
- Events: `keep_awake_refused` and `keep_awake_capped` (no properties), sent at most once per hold.
- FR-K7: `src/sw/deploy-config.test.ts` fails if `vercel.json` has a `Permissions-Policy` or `Feature-Policy` header that switches off `screen-wake-lock`, `notifications` or `push`, if any application source file sets such a header, or if a static `public/_headers` file appears.
- The stopwatch on `/app/tracker` holds the screen the same way (FR-K1 names both). Because `focus` imports `tracker`, the shared pieces live in their own web module, `keepawake` (`lib/wakeLock.ts`, `useWakeLock`, `useKeepAwake`, `KeepAwakeChip`); `focus` and `tracker` both import it through its barrel. `useKeepAwake` takes what the timer is doing (`running`, `focus`), applies the flag and the student's two switches, and reads them from `GET /focus/settings/` itself only when the page does not already have them. A stopwatch counts as focus time, and an unanswered "still studying?" prompt releases the lock like an away timer.

**Configure:** create the PostHog flag `keep_awake` (0% to start). No environment variable.

```bash
cd "$ROOT" && git switch main && git pull --ff-only && git switch -c feat/x-01-w2-6-keep-awake
cd apps/api && source .venv/bin/activate
python manage.py makemigrations --check --dry-run                # must say: No changes detected
pytest modules/focus -q && cd "$ROOT"
pnpm --filter @artha/web exec vitest run src/modules/keepawake src/modules/focus src/modules/tracker src/sw && pnpm check
curl -sI https://<your-web-domain>/app | grep -i permissions-policy       # after deploy; must not list screen-wake-lock
```

**Check on real devices** (PRD FR-K10), each with the screen timeout set to its shortest value, 30 seconds or one minute, and a 5-minute round (Settings, Focus: keep the "Keep the screen on during focus rounds" switch on):

1. Android Chrome: start a round, leave the phone alone. The chip says "Screen stays on" and the screen does not dim for the whole round. Press Pause: the screen dims after the timeout. Resume: it holds again.
2. iPhone, Home Screen app (iOS 16.4 or later): same as 1. If it does not hold, note the iOS version in `docs/X-01-spike-results.md`; the chip should then say "Screen may sleep" and nothing else breaks.
3. iPhone Safari tab, desktop Chrome, Edge, Firefox, Safari: same as 1 (desktop: set the display to sleep after one minute).
4. Switch to another tab during a round for a minute and come back: the chip returns to "Screen stays on" without a reload.
5. Turn on battery saver (Android) or low power mode (iPhone) and start a round: the chip says "Screen may sleep", with no error message.
6. With "Also keep it on during breaks" off, let a round end: the chip disappears for the break. Switch it on and repeat: the chip stays through the break.
7. A browser without the API (an old Firefox, for example): no chip, the settings page notes it, the timer works.
   Stopwatch (`/app/tracker`): repeat 1, 4 and 5 with the stopwatch. Pause releases the screen; leave it running until the "still studying?" prompt appears and the chip disappears and the lock is released; answer it and the chip returns.
8. Keyboard only through the Settings page switches, screen reader (the chip change is spoken once, politely), the four themes, 320 px width.

Production migration first (deploy order above). Roll back: flag `keep_awake` at 0%.

### W2.7 Launch hardening

Goal: be able to see problems before students do, then run the device matrix.

**What changed**

- Retention (FR-N24): `manage.py prune_notifications` (`services/retention.py`, rules in `domain/retention.py`) deletes deliveries 90 days after `attempted_at`, notifications 180 days after `created_at` (their deliveries go with them), jobs that are not pending 30 days after `updated_at`, and devices revoked more than 30 days ago (their delivery rows stay, with the device cleared). Each delete is its own transaction of at most 1000 rows, so no lock lasts long, and running it twice does nothing the second time. `--dry-run` prints counts and deletes nothing; `--batch` (at most 1000) and `--max-rows` bound a run. The sweep runs it by itself once a night, between 21:30 and 21:35 UTC (03:00 in India), at most 20,000 rows per run. Shown-message memory (`MessageShown`, 120 days) joined the job with W3.3; action tokens join with W3.6.
- Delivery check (FR-N23): every sweep run judges the last 15 minutes of push attempts (`sent` plus `failed`; suppressed and queued rows are not attempts) and, when fewer than 98% were accepted or the 95th percentile of lateness is over 5 seconds, logs the error `push_slo_breach` with `attempts`, `accepted_ratio`, `p95_ms` and which target failed. **A window under 5 attempts never counts** (one failure out of two is noise); the number is `MIN_SAMPLE` in `domain/slo.py`. A failing check is logged as `sweep_step_failed` and never stops jobs from firing.
- Sentry tags (FR-N23): every structured line carries `push_log` (its name) and, when it has one, `notification_event`, so an alert rule or a filter can pick `push_failed` or one event type.
- Logs: a test runs a send, a revoked device, a suppression and a sweep, and fails if any line holds an endpoint, a key, an auth secret or the notification text, or uses a forbidden field name.
- Declarative push (FR-N35): `NOTIFICATIONS_DECLARATIVE_PUSH=true` adds Safari's declarative fields (`web_push: 8030` and a `notification` object with an absolute `navigate` link) beside the worker fields; every other browser ignores them and the worker path is unchanged. **Leave it off until spike S3 passes on a real device.** It needs `NOTIFICATIONS_WEB_BASE_URL` (the web origin, https), and the API refuses to start with the switch on and no origin.
- Web analytics: nothing new. Every PRD section 10 event the web owns already exists (`alerts_step_*`, `push_permission_*`, `push_test_requested`, `push_device_removed`, `notification_pref_changed`, `push_clicked`, `local_alert_shown`); `inbox_opened` arrives with the inbox in W3.1 (done: `lib/analytics.ts`).

**Configure:** the Sentry alert rule and the PostHog dashboard (below), the sweeper (below), and optionally the two declarative variables.

```bash
cd "$ROOT" && git switch main && git pull --ff-only && git switch -c feat/x-01-w2-7-hardening
cd apps/api && source .venv/bin/activate
python manage.py makemigrations --check --dry-run          # No changes detected: this wave has no migration
python manage.py prune_notifications --dry-run             # prints counts per table, deletes nothing
python manage.py prune_notifications                       # run it once by hand; run it again: every count is 0
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

Targets: `accepted_ratio >= 0.98`, `p95_ms <= 5000`. The sweep also runs the same check over the last 15 minutes and logs an error (`push_slo_breach`) when it fails; in **Sentry** create an alert rule for the `artha-api` project: when an event's message starts with `push_slo_breach` (or the tag `push_log` equals `push_slo_breach`), notify you by email, at most once an hour. A second rule on the tag `push_log` equal to `sweep_step_failed` catches a broken check. In **PostHog** build one dashboard from `alerts_step_completed`, `push_permission_result`, `push_clicked`, `notification_pref_changed`.

**Device matrix** (sign off in `docs/X-01-spike-results.md` under a new heading "W2.7 device matrix"; paste this table and fill it in): Android Chrome, iPhone Safari tab (install guide), iPhone Home Screen app, desktop Chrome, Edge, Firefox, Safari. Each: allow, test push, timer-end push with the tab closed, pause cancels, blocked flow, remove device, keep awake (W2.6).

```
## W2.7 device matrix

| Device and version | Allow | Test push | Timer-end push, tab closed | Pause cancels | Blocked flow | Remove device | Keep awake | Signed off (date, initials) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Android Chrome | | | | | | | | |
| iPhone Safari tab (install guide) | | n/a | n/a | n/a | n/a | n/a | | |
| iPhone Home Screen app | | | | | | | | |
| Desktop Chrome | | | | | | | | |
| Edge | | | | | | | | |
| Firefox | | | | | | | | |
| Safari (macOS) | | | | | | | | |
```

Write pass, fail or the note ("late by 40 s") in each cell. Also on one device, with `NOTIFICATIONS_DECLARATIVE_PUSH` still off, repeat S3 and record the result: that decides whether the switch is ever turned on.

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

Goal: a push missed on the phone is readable in the app (FR-N8), with an unread count on a bell. No migration, no Realtime and no student-facing database policy: the bell polls through Django (PRD C7), and the Supabase Data API stays disabled as in `docs/SETUP.md` 2.4.

**What changed**

- API, `GET /notifications/inbox/` (`selectors/inbox.py`, `views/inbox.py`): the student's own notifications, newest first, cursor paged (`limit` 1 to 50, default 20), **never past the newest 50** visible rows (the cursor carries how many rows were served, so the cap holds across pages). The answer is `{results, next_cursor, unread_count}`; each result has `id, category, category_label, title, body, deep_link, read, created_at`. `unread_count` covers every visible unread item, not only the page.
- **Hidden and expired items are left out of the list and the count.** Expired means `expires_at` has passed. Hidden means the student switched that category off for the **inbox** channel in settings (the row still exists, so switching it back on shows it again); a push switch alone never hides anything. The test push has no switch and always shows. There is no new column.
- API, `POST /notifications/inbox/read/` (`services/inbox.py: mark_read`): body `{"ids": [...]}` (1 to 50 ids) or `{"all": true}`, exactly one of the two. It only touches the student's own visible unread rows, so another student's id, an unknown id, a hidden or an expired one is skipped without an error and never reveals anything. Idempotent; the first `read_at` is kept. The answer is `{"unread_count": n}`. Marking from the inbox does not mark pushes as clicked (only `?n=` and the click endpoint do).
- Both endpoints use the existing `NotificationsView`: signed-in only, `notifications_read` for the list and `notifications_write` for marking, and 403 `notifications_disabled` when the environment switch or the `notifications_ui` flag is off. A bad cursor or limit is a 400 (`bad_cursor`, or the field error).
- Erasure and export: nothing to change. `delete_all_for_user` already deletes every `Notification` and `export_all` already lists them, and a test now covers the inbox rows (FR-N25 holds).
- Web, `notifications` module: `BellContainer` (mounted in `SiteHeader` for signed-in students, so it is on every `/app` page; it renders nothing while the feature is off), `InboxContainer` at `/app/notifications` (one `h1`, "Inbox"), `InboxList`, `BellButton`, and the hooks in `hooks/useInbox.ts`.
- The bell asks for the unread count every 60 seconds while the tab is visible (`INBOX_POLL_MS`), on every window focus, and **at once when the service worker posts `artha:push-received` after showing a push**. The worker change is new in this wave (`src/sw/handlers.ts`, `messages.ts`): after `showNotification` it tells open pages that a push arrived, with no content at all, and a failure to tell them never affects the alert. `public/sw.js` is generated, so a deploy rebuilds it; open tabs pick the new worker up on their next visit.
- Opening an item reports `inbox_opened` (`category`, `seconds_since_sent`; never text, ids or links), marks it read, and follows its `deep_link` **only if it is an allow-listed relative path** (checked again on the page with the same rules as the worker). Anything else only marks the item read. A ctrl, cmd, shift or middle click is left to the browser, so "open in a new tab" works.
- Marking read updates the list and the bell at once, rolls back on a failure, and takes the server's count when the answer arrives.
- Accessibility: one `h1`; items are `h2`; the title is a real link; unread items say "New" in words and are bold (the left bar is decoration); a polite live region announces count changes (silent on first load) both on the bell and on the page; the bell link is named "Notifications, 3 unread notifications"; mark-read buttons are named per item; 44 px targets; no motion except the load spinner, which stops under reduced motion; colours are tokens only.
- Gate: the `notifications_ui` flag on the web (fails open) and the same flag on the API. When it is off the bell is gone, `/app/notifications` says "Notifications are not available yet", and the rest of the app is unchanged.

**Configure:** nothing new. The wave rides on `NOTIFICATIONS_ENABLED` and the `notifications_ui` flag already set up in W2.

```bash
cd "$ROOT" && git switch main && git pull --ff-only && git switch -c feat/x-01-w3-1-inbox
cd apps/api && source .venv/bin/activate
python manage.py makemigrations --check --dry-run          # No changes detected: this wave has no migration
pytest modules/notifications -q && ruff check . && ruff format --check . && cd "$ROOT"
pnpm --filter @artha/web exec vitest run src/modules/notifications src/sw && pnpm check
```

**Roll back:** set the PostHog flag `notifications_ui` to 0% (the bell disappears and both endpoints answer 403 within about a minute), or set `NOTIFICATIONS_ENABLED=false` and redeploy. Nothing is deleted, no database change is involved, and pushes keep working because they do not depend on the inbox screens. To undo the code, revert the wave's commit: the worker's extra message is ignored by older pages.

**Check on real devices** (after deploy, with `notifications_ui` on for you):

1. Desktop Chrome, signed in with a device registered: the bell shows in the header. Send a test push from Settings, Notifications. With the tab open the count rises at once (not after a minute); with the tab hidden for a minute, switch back and it is current.
2. Open `/app/notifications`: the test push is listed with "New". Click its title: you land on `/app/settings/notifications` and the item is read; go back and the bell is one lower.
3. "Mark all as read" sets the bell to nothing and disables the button. The check button on a single row marks only that row.
4. Android Chrome: receive a timer push with the app closed, open the app, and the inbox lists it even if you never tapped the push. Tap a push with the app already open: you land on the page and the bell drops.
5. iPhone Home Screen app: same as 4, then pull the app to the background for two minutes and bring it back; the count is current.
6. Settings, Notifications: switch a category off for the inbox. Its items leave the list and the count; switch it back on and they return.
7. Ctrl or cmd click an item title: it opens in a new tab and the item is read in the first.
8. Keyboard only: Tab to the bell, Enter, Tab through titles and mark-read buttons; screen reader: the count change after a new push is spoken once, politely, and not on page load.
9. Reading, Light, Dark and System themes at 320, 390, 768 and 1280 px: no horizontal scroll, the badge never covers the bell icon or the account button, 200% zoom still works.
10. Turn `notifications_ui` to 0%: the bell is gone, `/app/notifications` shows the "not available yet" message, and the focus timer, tracker and coverage pages work as before.

### W3.2 Tracker alerts and deferred delivery

Goal: three alerts from the time tracker (a stopwatch left running, the daily goal reached, a streak about to break) and the second half of the policy, FR-N33: a push that quiet hours or the daily cap holds is delivered later instead of being lost. No migration: `stopwatch_long` and `deliver_deferred` were already job kinds in the W2.1 schema. No web change: `/app/tracker` is already on the deep-link allow-list (worker and API agree, covered by the existing parity test).

**What changed**

- `tracking` announcers (`tracking/events.py`): `announces_stopwatch` and `announces_goal` decorate the public actions in `tracking/services.py`. After commit, a stopwatch whose (`client_id`, state, counted seconds) moved emits `stopwatch_changed`; a day whose goal went from not met to met emits `goal_reached` (once per transition, not on every write). A rolled-back action and a no-op emit nothing, and nested calls announce once. `tracking/domain/judgement.py` is the pure rule (`judge_running`, `reaches_at`, with a 5 second early tolerance) and `selectors.stopwatch_running_judgement` is the read-only selector (FR-N18).
- `stopwatch_long`: planned by `scheduling/planning.plan_stopwatch_long` when a stopwatch starts or resumes, to fire when its **counted time** reaches 3 hours (paused time does not count). Pause, stop, discard, or a new run supersedes the job (`cancel_for_stopwatch`); when the job fires, `StopwatchLongHandler` re-reads the run and sends only if it is still running and has really reached the threshold, otherwise it is skipped or re-planned for the new moment. Dedupe key `stopwatch_long:{client_id}`, expiry 1 hour. The threshold has no setting.
- `goal_reached`: created by `subscribers.on_goal_reached`, dedupe key `goal:{local_date}` (one per student per local day), expiry 6 hours, and delivered by a `deliver_deferred` job 2 seconds later (`IMMEDIATE_DELAY`) so the request that crossed the goal never waits on a push. Quiet hours therefore hold it like any other alert.
- `streak_at_risk`: a new sweep step (`scheduling/streak_alerts.send_streak_alerts`, after `fire_overdue_jobs`, bounded and guarded like the others) finds students with a live streak and no qualifying study today, whose local time is in the lead window before their day ends (`domain/tracker_alerts.streak_window`). Dedupe key `streak:{local_date}`, expiry 3 hours. Reads go through `tracking.selectors.streaks_at_risk` in batches of 500; a student whose goal is met, whose streak is zero, or who has switched the category off is never alerted.
- Deferred delivery (FR-N33): `services/notify.deliver` runs the policy once; on DEFER it plans one `deliver_deferred` job (`planning.plan_deferred`) for the policy's `deliver_at`. `DeliverDeferredHandler` re-judges when the job fires: still unread, not expired, flag and master switch on, preferences unchanged. If the policy still defers (a new quiet window, the cap), it re-plans, at most `MAX_DEFERRALS` (5) times, then drops the notification with `push_dropped`. Past `expires_at` it is dropped. If the environment or the `notifications_send` flag is off when the job fires, the held row is closed (`dispatch.close_held`) and a `push_deferred`/`push_dropped` log line says why. The inbox row exists from the start, so a held alert is readable in the bell either way.
- Copy: three builders in `domain/copy.py` (`stopwatch_long`, `goal_reached`, `streak_at_risk`), all linking to `/app/tracker`.
- Priority and quiet hours: all three are priority 1, so quiet hours hold them (they are not exempt) and a priority 1 alert may use one slot beyond the daily cap of 3.
- Per-student isolation: every job, dedupe key and query is scoped by student; one student's failure in the streak sweep is logged and skipped without stopping the batch.

**Configure:** nothing new. The alerts ride on `NOTIFICATIONS_ENABLED`, the `notifications_send` flag (strict) and the existing per-category settings. The sweep step needs the per-minute sweep from W2.3 to be running.

```bash
cd "$ROOT" && git switch main && git pull --ff-only && git switch -c feat/x-01-w3-2-tracker-alerts
cd apps/api && source .venv/bin/activate
python manage.py makemigrations --check --dry-run          # No changes detected: this wave has no migration
pytest modules/tracking modules/notifications -q && ruff check . && ruff format --check . && cd "$ROOT"
pnpm check
```

**Roll back:** add the event keys to `NOTIFICATIONS_DISABLED_EVENTS`, for example `stopwatch_long,goal_reached,streak_at_risk` (any subset), and redeploy; the announcers still run but nothing is created. Setting the `notifications_send` flag to 0% or `NOTIFICATIONS_ENABLED=false` stops all delivery, and already-held `deliver_deferred` jobs close themselves when they fire. Nothing is deleted and no database change is involved. To undo the code, revert the wave's commit; pending jobs of the new kinds are skipped by older code as unknown.

Check the held alerts with:

```sql
select kind, status, fire_at, attempts from notifications_scheduledjob
where kind in ('deliver_deferred', 'stopwatch_long') order by created_at desc limit 10;
```

**Check on real devices** (after deploy, with the flags on for you):

1. Quiet hours set around now (`PUT settings/` as in W2.1): reach the daily goal. No push appears; the inbox shows the alert; a `deliver_deferred` job exists with `fire_at` at the end of the window. At that time the push arrives once.
2. Goal reached at 06:00 with default quiet hours (22:00 to 07:00): the push arrives at 07:00, not at 06:00. Cross the goal again the same day: nothing new (one per day).
3. Start the stopwatch and leave it for 3 counted hours (or shorten the job's `fire_at` in the database): one push, "still running". Pause before 3 hours, wait past the original time: nothing.
4. Streak at risk: a student with a streak and no study today, local time 20:30, default quiet hours: the push arrives about 90 minutes before the day ends. With the goal already met: no push.
5. With QStash configured, cross the goal and confirm the push arrives within a few seconds, not at the next sweep minute.
6. Switch the Tracker category off for push: none of the three arrive; the inbox follows the inbox switch.
7. Add `goal_reached` to `NOTIFICATIONS_DISABLED_EVENTS`, redeploy, reach a goal: nothing is created.
8. Tap each push: you land on `/app/tracker` and the bell drops.

**Decisions**

- A student's "day end" for the streak alert is the start of their evening quiet window, with a floor of 16:00 local, because with default quiet hours a 22:30 alert would always be held until morning, after the streak had already broken.
- The goal alert goes through a `deliver_deferred` job 2 seconds out rather than inline, so a push provider outage cannot slow a tracker write.
- The stopwatch threshold counts running time only, and has no setting.

### W3.3 Daily thought and nudge

Goal: one short motivational line a day, shown in the app (a card on `/app`) and sent once as the daily nudge push, from a library that editors write and publish in the Django admin. One migration (`0002_motivation`: `Message` and `MessageShown`). `NOTIFICATIONS_DECLARATIVE_PUSH` stays off.

**What changed**

- Library: `Message` (body up to 240 characters, optional attribution, course and level or generic, tone, phase `far`/`near`/`final_week`/`exam_day`/`any`, language `en`, status `draft`/`published`/`retired`, `seed_key`). A published message must have `published_at`. `MessageShown` records what a student was shown, one row per student per local day (unique on `user_id`, `shown_on`), with the channel (`inapp` or `push`).
- Editors: Django admin, Notifications, Messages. New lines start as drafts; the actions "Publish selected" and "Retire selected" call `services/motivation.publish` and `retire`, which refuse a line that fails the checks (empty, over 240 characters, a course and level that do not match). Once a line is not a draft its text and targeting are locked; only drafts can be deleted. Nothing is ever sent from a draft.
- Seed: `manage.py load_motivation_seed` reads `seed/motivation/*.json` (126 short original lines: 36 generic, 9 for each of the ten levels). It loads drafts only, matches rows by `seed_key`, never overwrites or publishes an existing row, and skips (and reports) a course or level that is missing. Safe to run twice.
- Thought: `GET /notifications/thought/today/` (`ThoughtTodayView`, throttled like the other notification reads, behind the `notifications_ui` flag; 403 `notifications_disabled` when off or when the student switched the motivation inbox off). The first call of the student's local day picks one published line and records it; every later call that day returns the same one. Response: `{"thought": null}` or `{"thought": {"id", "body", "attribution", "shown_on"}}`.
- Choice (`domain/motivation.choose`, pure): a line never repeats for the same student within 60 days (shown on day D, it can return on D + 60). The pool is narrowed by the exam phase (a `final_week` line only in the last seven days; no exam date means `any` lines only), preferring the student's tone, then relaxing it: tone and phase, tone and any phase, any tone and phase, any tone and any phase. The pick inside a tier is a hash of student and date, so a retry chooses the same line. When every fitting line was seen in the last 60 days, or none fits, the answer is "exhausted" or "empty": nothing is shown or sent and nothing is repeated to fill the gap (the card hides, no push).
- Nudge schedule: `NotificationSettings.next_nudge_at` is kept per student from the time zone, the nudge time and the master and category switches (`domain/nudge.schedule_nudge`, `zoneinfo`). A time that does not exist on the day the clocks go forward is sent at the first moment after the gap; a repeated hour is sent once. Changing the zone, the time or a switch recomputes it; a student who has none gets one from a bounded backfill (200 rows per sweep minute) and from the permission journey.
- Nudge sweep: `scheduling/nudges.send_daily_nudges`, after the streak step, guarded and bounded like the others (batches of 100, oldest due first, one student's failure is logged by error type and skipped). Per student `services/nudge.process_due_nudge` claims the row with a compare-and-set on `next_nudge_at` (so two overlapping sweeps send at most one), judges it read-only (`judge_nudge`: more than 6 hours late is stale, skipped and re-planned), checks the strict `notifications_send` flag, reserves a line (channel `push`), creates the notification and calls `notify.deliver`. Dedupe key `nudge:{local_date}` is the second guard.
- Visited today: `daily_nudge` has `skip_if_opened`. In the policy, a student who opened the app on their local day gets `push_suppressed` with reason `visited_today`, and the inbox hides that row. "Opened" means a last-visit report from the web (sent when the tab hides) or a thought card fetch that day. The rule sits in the policy, so the deferred re-judge honours it too: a visit during quiet hours cancels the later push.
- Existing rules all apply to the nudge: priority 3 (held by quiet hours, subject to the daily cap), master switch, category and channel preferences, `NOTIFICATIONS_DISABLED_EVENTS`, the deep-link allow-list (`/app`).
- Retention and privacy: `MessageShown` rows are pruned after 120 days by `prune_notifications` (`messages_shown` in its report), deleted with the account (`messages_shown` in the erasure count) and listed in the account export as `daily_thoughts`.
- Web: `useTodayThought` (notifications barrel) and a `ThoughtWidget` on `/app` in the workspace module, an independent card with its own skeleton, error and Try again. It hides itself when the flag is off, the server says notifications are disabled, or there is no line. Design-system tokens and the `Sparkles` icon only.

**Configure:** nothing new. The thought and the nudge ride on `NOTIFICATIONS_ENABLED`, the `notifications_ui` flag (card) and the strict `notifications_send` flag (push). The nudge needs the per-minute sweep from W2.3.

```bash
cd "$ROOT/apps/api" && source .venv/bin/activate
python manage.py makemigrations --check --dry-run          # No changes detected once 0002_motivation exists
python manage.py migrate
python manage.py load_motivation_seed                      # drafts only; safe to run twice
pytest modules/notifications -q && ruff check . && ruff format --check . && cd "$ROOT"
pnpm check
```

Production: migrate first, merge, then run `python manage.py load_motivation_seed` against production the same way as the migration (section 3 environment). Then an editor opens `https://api.<your-domain>/<DJANGO_ADMIN_PATH>/`, Notifications, Messages, reviews the drafts, selects them and runs "Publish selected". Until then the card and the nudge have nothing to show and stay quiet.

**Roll back:** add `daily_nudge` to `NOTIFICATIONS_DISABLED_EVENTS` and redeploy to stop the push (the sweep still plans the next time but creates nothing); set the `notifications_ui` flag to 0% to hide the card; retire lines in the admin to take them out of rotation. Setting `notifications_send` to 0% or `NOTIFICATIONS_ENABLED=false` stops all delivery. To undo the code, revert the commit; the two new tables can stay, because older code ignores them and `0002_motivation` only adds tables.

Check what was shown and sent with:

```sql
select user_id, shown_on, channel, message_id from notifications_messageshown order by created_at desc limit 10;
select user_id, next_nudge_at from notifications_notificationsettings where next_nudge_at is not null limit 10;
select status, suppress_reason, attempted_at from notifications_delivery d
join notifications_notification n on n.id = d.notification_id
where n.event = 'daily_nudge' order by d.attempted_at desc limit 10;
```

**Check on real devices** (after deploy and after an editor published at least one line for your course and level):

1. Open `/app` for the first time today: one "A thought for today" card. Reload and come back later: the same line. The next day: a different one.
2. In the SQL editor `update notifications_settings set next_nudge_at = now() where user_id = '<your uuid>';`, close the app without opening `/app` that day (or use another account), then run the sweep (section 3, W2.3 curl): one push, "A thought for today", and tapping it opens `/app`. `next_nudge_at` moves to tomorrow. Run the sweep again: nothing new.
3. Repeat step 2 on an account that opened `/app` today: no push; the delivery row is `suppressed` with reason `visited_today`, and the inbox does not show the nudge.
4. Change the time zone or the nudge time in settings: `next_nudge_at` moves to the next occurrence in the new zone.
5. Quiet hours around now: the nudge is held and arrives at the end of the window, unless you open the app first, in which case it never arrives.
6. Turn the Motivation category off for push: no nudge. Turn the Motivation inbox switch off: the card disappears.
7. Add `daily_nudge` to `NOTIFICATIONS_DISABLED_EVENTS`, redeploy, run the sweep: nothing is created.
8. Check all four themes and widths from 320 to 1280 px for the card.

**Decisions**

- Visited today uses the existing last-visit report plus the thought card fetch, because the report is sent only when the tab hides and a student who is still reading `/app` would otherwise get a nudge.
- The visited rule lives in the policy rather than the sweep, so the deferred re-judge applies it as well.
- A nudge more than 6 hours late (the sweep was down) is skipped, not sent, and the next one is planned; this is the catalogue's expiry for `daily_nudge`.
- Sending is claim-first (compare-and-set on `next_nudge_at`) rather than holding row locks during a network call; the dedupe key is the backstop.
- When the library is exhausted or empty, nothing is shown or sent. Repeating a line inside 60 days was judged worse than a quiet day.
- Seed lines are original and short (at most 82 characters, plain ASCII), with no quotations, so there is no copyright question and no attribution is needed.

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
| `NOTIFICATIONS_DECLARATIVE_PUSH`, `NOTIFICATIONS_WEB_BASE_URL` | | yes | no | P2 (W2.7, off until spike S3 passes) |
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
