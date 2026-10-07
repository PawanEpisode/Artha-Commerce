# X-01 Notifications, floating timer, keep awake: build and rollout runbook

Companion to `docs/product/prd/X-01.1-push-notifications.md` (waves, requirements) and `docs/product/erd/X-01.1-push-notifications.md` (tables). Same style as the other `docs/*-ROLLOUT.md` files, but organised **phase by phase** with the exact steps and commands, split into **web**, **api** and **other tools**. Phases and waves use the numbering in PRD section 0 and 13.

| Phase | What | Flags |
| --- | --- | --- |
| P1 | Spikes on real devices | none |
| P2 | Alerts core (waves W2.1 to W2.7), includes keep awake | `push_notifications`, `keep_awake` |
| P3 | More alerts (waves W3.1 to W3.7) | `push_notifications` |
| P4 | Floating timer (waves W4.0 to W4.5) | `floating_timer` |
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

**Roll back:** add `daily_nudge` to `NOTIFICATIONS_DISABLED_EVENTS` and redeploy to stop the push (the sweep leaves the due rows untouched; when the event is switched back on, anything more than 6 hours overdue is skipped as stale and replanned, so there is no burst); set the `notifications_ui` flag to 0% to hide the card; retire lines in the admin to take them out of rotation. Setting `notifications_send` to 0% or `NOTIFICATIONS_ENABLED=false` stops all delivery. To undo the code, revert the commit; the two new tables can stay, because older code ignores them and `0002_motivation` only adds tables.

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

Goal: three more alerts on the machinery of W3.1 to W3.3: exam countdown milestones, revision that is due, and new content for a course. No migration, no web change (`/app` and `/app/revision` are already on the deep-link allow-list). `NOTIFICATIONS_DECLARATIVE_PUSH` stays off.

**What changed**

- One daily slot. Revision and the exam countdown do not get their own sweep step: they share the student's nudge time (`next_nudge_at`, W3.3) with the thought. `services/nudge.process_due_nudge` still claims the due time first (at most once), then `domain/daily_slot.choose` picks what the slot carries: an exam milestone, else revision if a chapter is due, else the daily thought. A student therefore never gets a thought and a revision reminder together. A category the student turned off for push, or an event on `NOTIFICATIONS_DISABLED_EVENTS`, is skipped so the next one goes out.
- `exam_milestone`: on the exact local day the exam is 60, 30, 14, 7, 3 or 1 days away (`domain/daily_slot.MILESTONES`). Dedupe key `exam:{days_left}`, category exam, priority 2, expiry 12 hours. It is not skipped after a visit. A milestone is tied to its day: if the day is missed (sweep down, push held past expiry) it is not owed. Copy (`domain/copy`): "{n} days to your exam" (the last one reads "Your exam is tomorrow"), one calm line per milestone, links to `/app`.
- `revision_due`: when `coverage.selectors.due_for_revision` has at least one chapter for today. Dedupe key `revision:{local_date}`, category revision, priority 2, expiry 12 hours. It replaces the thought that day and is skipped with `visited_today` when the student already opened the app (the same signal as the nudge, `skip_if_opened`). Copy names how many chapters are due and the one to start with (overdue first, then the heaviest); links to `/app/revision`. A revision push displaced by a milestone is not lost: the chapters are still due tomorrow and the same rule offers it then.
- Reads: `selectors/daily.py` (`daily_facts`, `push_allowed`) reads through `coverage`'s public selectors and the student's own preferences; nothing reaches into another module's tables.
- `content_published`: `core.events.CONTENT_PUBLISHED` is the event; the module that owns the content emits it once, after the item is live, with `item_id`, `title`, `level_id` or `course_id` and an optional `link`. `subscribers.on_content_published` calls `services/content.announce`, which pages through `coverage.selectors.audience_user_ids` (500 at a time, at most 5000 students per announcement), creates one notification per student (dedupe key `content:{item_id}`, category content, priority 3, expiry 24 hours) and plans a `deliver_deferred` job 2 seconds ahead, so no push is sent inside the publisher's request. Nothing publishes the event yet, so students see nothing until the publishing module exists. An announcement with no audience, no title or id, a link off the allow-list, or while a switch is off does nothing.
- The 2 second delay moved to `scheduling/planning.IMMEDIATE_DELAY` so the goal alert and the content fan-out share one constant.
- Kill switches: `exam_milestone`, `revision_due` and `content_published` can each be listed in `NOTIFICATIONS_DISABLED_EVENTS`. Listing `daily_nudge` stops the whole slot (thought, revision and milestones), because the slot is driven by it.

**Configure:** nothing new. All three ride on `NOTIFICATIONS_ENABLED`, the strict `notifications_send` flag and the per-category switches (Revision, Exam countdown, New content). The slot needs the per-minute sweep from W2.3.

```bash
cd "$ROOT/apps/api" && source .venv/bin/activate
python manage.py makemigrations --check --dry-run          # No changes detected: this wave has no migration
pytest modules/notifications modules/coverage -q && ruff check . && ruff format --check . && cd "$ROOT"
pnpm check
```

**Roll back:** add `exam_milestone`, `revision_due` or `content_published` (any subset) to `NOTIFICATIONS_DISABLED_EVENTS` and redeploy; the slot falls back to the thought and the content listener creates nothing. `notifications_send` at 0% or `NOTIFICATIONS_ENABLED=false` stops all delivery. Nothing is deleted and no database change is involved. To undo the code, revert the commit.

Check what was sent with:

```sql
select event, dedupe_key, created_at from notifications_notification
where event in ('exam_milestone', 'revision_due', 'content_published') order by created_at desc limit 20;
select n.event, d.status, d.suppress_reason from notifications_delivery d
join notifications_notification n on n.id = d.notification_id
where n.event in ('exam_milestone', 'revision_due') order by d.attempted_at desc limit 20;
```

**Check on real devices** (after deploy, with the flags on for you; use a student with an active enrolment):

1. Exam countdown: set the exam date in coverage settings to exactly 30 days ahead (or 60, 14, 7, 3, 1). Force the nudge as in W3.3 (`update notifications_settings set next_nudge_at = now() where user_id = '<your uuid>';`, then run the sweep). One push, "30 days to your exam", opening `/app`. Run the sweep again: nothing new.
2. Revision: with an exam date that is not a milestone and at least one chapter due, force the nudge without opening `/app` that day: one push, "Revision due", opening `/app/revision`, and no thought that day. With no chapter due: the thought arrives instead.
3. Both at once (milestone day and a chapter due): exactly one push, the milestone. The next day, the revision push arrives.
4. Open `/app` first, then force the nudge: no revision push (`visited_today`), but an exam milestone still arrives.
5. Turn the Exam countdown category off for push on a milestone day with chapters due: the revision push goes out instead. Turn both off: the thought goes out.
6. Quiet hours around now: the push is held and arrives when they end.
7. Add `exam_milestone` to `NOTIFICATIONS_DISABLED_EVENTS`, redeploy, force a nudge on a milestone day: no milestone push.
8. Content: from the Django shell run `from core import events; events.emit("content_published", item_id="test-1", title="Test amendment", level_id="<your level id>")`. Each student on that level gets one push within a few seconds (a queue) or at the next sweep minute; run it again: nothing new. Use a level with only test accounts.

**Decisions**

- The exam countdown uses 60, 30, 14, 7, 3 and 1 days (the first draft of the PRD said milestones without numbers). The exam day itself is left to the thought.
- Revision, the exam countdown and the thought share one slot at the student's nudge time and the order is exam, revision, thought. This reads the PRD's "one revision push a day, never two" as one daily push from the family, which is also why the earlier rollout check of "one milestone push and one revision push that day" is now "one push that day, the other the next day".
- Revision is skipped after a visit because the student has already seen what is due; the exam milestone is not, because it is a one-off marker.
- `exam:{days_left}` is unique per student and number and notifications are kept 180 days, so an exam date that comes round again after a new cycle reuses a number only after the old row is pruned. A student who moves their exam date forward on the same days-left number inside 180 days will not get that one again.
- The content fan-out is bounded in one request (5000 students, a logged error `content_audience_truncated` beyond that, and announcing again picks up the rest). It is meant for the first releases; a publishing module with large cohorts should move it to a cursor job.

### W3.5 Weekly email

Goal: the first email the API sends itself. A weekly summary of the student's study, on Sunday at 18:00 in their own time zone, with a one-click unsubscribe that needs no login. It rides on the same per-minute sweep as the nudge, but email is its own small pipeline: it has no devices, quiet hours or daily cap, and a mail failure never touches a push device. One migration (`0003_weekly`), one new public web page (`/unsubscribe`). `NOTIFICATIONS_DECLARATIVE_PUSH` stays off.

**What changed**

- Schedule: `notifications_settings.next_weekly_at` (new column, partial index) holds the next Sunday 18:00 in the student's `timezone`, strictly after now and DST safe (`domain/weekly.next_weekly_at`). It is set when a settings row is created, moves when the time zone changes, and the sweep heals rows that have none (`backfill_next_weekly`, 200 a run). It does not depend on the category switch: whether the student wants the email is judged when it falls due.
- Sweep step `scheduling/weekly.send_weekly_emails` (after the nudge step, guarded like the others) finds rows with `next_weekly_at <= now` in batches of 100, oldest first, and hands each to `services/weekly.process_due_weekly`. That claims the due time with a compare-and-set (moved to the following Sunday before anything is sent, so two sweeps never both send), skips a week more than 24 hours late (`stale`), reads the week, and skips it when there is nothing to say.
- What is in it: the seven local days ending that Sunday. Study time and days studied (`tracking.selectors.day_totals`), the streak (`tracking.selectors.streak`), syllabus covered (the level roll-up percent from `coverage.selectors.overview`, 0% before any progress), chapters due for revision, and days to the exam when there is one. A week with no study time and nothing due for revision is skipped entirely (`domain/weekly.worth_sending`); no email and no inbox row.
- Notification and inbox: a `weekly_summary` notification is created once per ISO week (dedupe key `weekly:2026-W41`), category Weekly summary, linking to `/app/tracker`. It shows in the inbox when the student keeps the inbox channel on for that category. It is never pushed.
- Email policy (`domain/email_policy.decide_email`): the kill switches, then the master switch and the Weekly summary email switch (default on), then an address on the profile (`profiles.selectors.email_of`), then lateness. Each outcome is one `Delivery` row, channel `email`, no device; a suppression stores its reason (`flag_off`, `preference`, `no_address` (new), `stale`).
- Channel: `channels/email.py` (`EmailMessage`, `DjangoEmailChannel`, `FakeEmailChannel`), registered as `email`. It sends multipart (plain text and HTML) through Django's mail backend. A missing sender raises `ChannelNotConfigured` (a deployment mistake).
- Words and layout: `domain/email_copy.py` (subject "Your week: 5 h 20 min of study", plain text, HTML with every value escaped) on the same table layout as the auth emails. Colours are the fixed hex values of `domain/email_brand.py`, the sanctioned exception to "no raw hex"; a test reads `packages/email-templates/src/brand.ts` and fails when the two drift.
- Failures: a failed send is retried 15 minutes later, up to 3 attempts in all (the count lives on the delivery row), then the week is dropped. A missing configuration puts the due time back 15 minutes and is counted as a failed run, so the problem shows in the sweep log.
- Unsubscribe: every email carries `List-Unsubscribe: <https://<api>/api/v1/notifications/unsubscribe/?t=...>` and `List-Unsubscribe-Post: List-Unsubscribe=One-Click` (RFC 8058), and a footer link to `<web>/unsubscribe?t=...`. The token is stateless (HMAC of the student and category with `DJANGO_SECRET_KEY`), never expires and cannot be forged. `GET` describes the link, `POST` switches the email off (a normal preference change, so the student can turn it back on in settings). It works with no login, is throttled (20 a minute per address, `notifications_unsubscribe`) and still works when `NOTIFICATIONS_ENABLED` is false. The web page asks for one click instead of acting on load, so a mail scanner that opens the link cannot unsubscribe anyone; it is `noindex` and disallowed in `robots.txt`.
- Exam date: one rule for "when is the exam", `coverage.selectors.exam_date_of` (the student's own date, else the start of the term they chose). The weekly email, the exam countdown and the daily thought now use it. Before this, a student who only picked a term got no countdown or exam-phase thought.

**Configure** (API project, section 8 lists them): the provider already chosen in `docs/SETUP.md` 2.3.1 with SPF, DKIM and DMARC in place.

```bash
export EMAIL_HOST=smtp.resend.com EMAIL_PORT=587 EMAIL_HOST_USER=resend EMAIL_USE_TLS=true
export EMAIL_HOST_PASSWORD='<provider api key>'                    # secret
export NOTIFICATIONS_EMAIL_FROM='ArthaCommerce <no-reply@mail.<your-domain>>'   # empty disables sending
# also needed by the links in the email: NOTIFICATIONS_WEB_BASE_URL (the web origin) and NOTIFICATIONS_PUBLIC_BASE_URL (the API origin)
cd "$ROOT/apps/api" && source .venv/bin/activate
python manage.py migrate                                           # 0003_weekly
python manage.py sendtestemail you@example.com                     # Django built-in; must land in the inbox, not spam
pytest modules/notifications modules/coverage -q && ruff check . && ruff format --check . && cd "$ROOT"
pnpm check
```

Add the variables to the Vercel API project (`npx vercel env add ...` as in section 1; the password is a secret). The migration is additive (one nullable column, one index, a wider choices list that is not a database check), so it can go out before the code that uses it.

**Roll back:** add `weekly_summary` to `NOTIFICATIONS_DISABLED_EVENTS` and redeploy: the step does nothing and no email is sent. `notifications_send` at 0% or `NOTIFICATIONS_ENABLED=false` stops it as well; the unsubscribe link keeps working. Nothing is deleted. To undo the code, revert the commit; the extra column is harmless and can stay.

Check what was sent with:

```sql
select n.dedupe_key, d.status, d.suppress_reason, d.attempt, d.error_code, d.attempted_at
from notifications_delivery d join notifications_notification n on n.id = d.notification_id
where d.channel = 'email' order by d.attempted_at desc limit 20;
select count(*) filter (where next_weekly_at is null) as unplanned, count(*) as total from notifications_settings;
```

**Check on real devices and inboxes** (use a student with a real address, a week of study and the flags on for you):

1. Force it: `update notifications_settings set next_weekly_at = now() where user_id = '<your uuid>';` then run the sweep (or wait a minute). One email arrives with the subject "Your week: ...", looks right in light and dark mode, on a phone and in Gmail and Outlook, and the button opens `/app`. Run the sweep again: nothing new.
2. Open the inbox: a "Your week in Artha" row. Turn the Weekly summary inbox switch off and it disappears.
3. In Gmail, "Unsubscribe" appears next to the sender name; use it. Then check `select * from notifications_preference where category = 'progress'` shows an `email` row with `enabled = false`, and force another weekly: no email, a `suppressed` delivery with `preference`.
4. Open the footer link in the email: the page names the weekly summary and asks for one click. A link with a letter changed shows "This link is not valid".
5. Turn the Weekly summary email switch off in settings, force it: no email. Turn push off entirely (master switch): no email either.
6. A student with no study and nothing due: force it, no email and no inbox row.
7. Check the headers of a received message (Gmail, "Show original"): `List-Unsubscribe`, `List-Unsubscribe-Post`, and SPF, DKIM and DMARC all pass.
8. Set `NOTIFICATIONS_EMAIL_FROM` empty on a preview deploy and force it: the sweep log shows a failed run and the week is retried 15 minutes later once it is set again.

**Decisions**

- Sunday 18:00 local, covering the seven days that end that Sunday. Chosen with you; the PRD said "weekly" with no time.
- Audience is everyone whose Weekly summary email switch is on (the default), no push device needed, which is how the PRD reads email as the fallback. The master switch also stops it, because the ERD defines it as the switch for push and email. A student who has no settings row yet is not reached until one exists (a settings change, the permission step or a device registration creates it, and the sweep then plans their first Sunday); rows are not created in bulk. If you want every student from the first Sunday, a one-off insert of settings rows for all profiles does it, and the sweep plans the rest.
- Content is study time, streak, syllabus covered, revision due and days to the exam; a week with no study and nothing due is skipped, so nobody gets a "you did nothing" email. Syllabus covered is the simple percentage (not the weighted one).
- Email is deliberately outside the push policy: no quiet hours, no daily cap, no device health. It does not count towards the push cap.
- The unsubscribe token is signed with `DJANGO_SECRET_KEY`. Rotating that key invalidates the links in emails already sent; they then show the not-valid page and the student can use settings instead.
- Bounces and spam complaints are handled by the provider's suppression list; the API does not read them yet, so a student who bounces keeps being tried weekly until the provider suppresses the address.

### W3.6 Android notification buttons

Goal: the timer alert on an Android phone carries buttons, and a tap changes the timer without opening the app. Each button holds a one-time token that works once, for ten minutes, for the one timer phase the alert was about. One migration (`0004_actiontoken`), one public endpoint (`POST /api/v1/notifications/actions/`), no new environment variable. `NOTIFICATIONS_DECLARATIVE_PUSH` stays off.

**What changed**

- Buttons per alert (`domain/actions.buttons_for`): a round that reached its target and runs on in overtime (the default) gets **Start break** and **Pause**; a round that closed with its break waiting (breaks do not start by themselves) gets **Start break**; a round whose break begins by itself gets none; **break over** gets **Start round N**. A paused confirmation carries **Resume**. A round the student was away for gets no buttons (only the app can ask whether they studied through it). No "+5 min": focus refuses an extension once a round is past its target, which is always the case when the alert fires.
- Tokens: `notifications_actiontoken` (ERD 2.8) stores the SHA-256 of a 32-byte random token (base64url, 43 characters), the student, the notification, the timer phase (`timer_client_id`, `timer_version`), the action, `expires_at` (10 minutes after the alert) and `used_at`. The token itself is only in the push; it is never stored or logged. Tokens are minted when the alert is sent, once per send, and only when at least one of the student's active devices has platform `android`; other devices get the same alert without buttons (`dispatch._message_with_buttons`). If buttons would push the payload past 3 KB they are dropped (logged `push_buttons_dropped`); with two buttons it is under 1 KB.
- Use (`services/actions.tap`): one atomic `UPDATE ... WHERE token_hash = %s AND used_at IS NULL AND expires_at > now` spends the token, so a replay or a second tap racing the first does nothing. The tap then goes to `focus.services.act_from_notification` with the phase and version from the token. A timer that moved since (paused or stopped in the app, another round) is left untouched (`stale`). The tap marks the notification read and its pushes clicked.
- Presence: a tap within two minutes after the round's end counts as the student being there (`focus.domain.timing.present_by_tap`, the same window as the tab heartbeat), so a phone that was locked through the round can still start the break. A later tap on a round nobody saw end answers `needs_app` and changes nothing; the app then asks the usual "did you study through it?".
- Focus: `act_from_notification` is a new public, announcing service action (one `timer_changed` per tap that moves the timer). `start`, `pause`, `resume` and `end` were split into a thin public wrapper and an internal function so the button action reuses them without announcing twice. The timer-end judgement now also says whether the break starts by itself.
- Endpoint: no sign-in (the service worker has none), the token in the JSON body is the credential. Malformed, unknown, used and expired tokens get one answer: `400 {"error": {"code": "action_unavailable", ...}}`. `403 notifications_disabled` when notifications are off, the student's `notifications_send` flag is off, or the button kill switch is set. Throttled at 30 a minute per address (`notifications_action`, plus the anonymous 60 a minute). CORS stays limited to `CORS_ALLOWED_ORIGINS` (the web origin). Sentry drops the body of this path and filters any key named `token` anywhere in request data and frame variables.
- Answer: `200 {"outcome": "done" | "already" | "stale" | "needs_app", "notification": {title, body, tag, url, actions}}`. The service worker shows it in place of the alert (same tag), so the student sees "Timer paused" with a Resume button, "Break started", "Nothing changed" or "Open the app". Any failure (offline, refused, switched off) shows "Open the app" with the alert's link. Only a tap on the notification itself opens the app; `?n=<id>` click tracking is unchanged.
- Worker: `src/sw/actions.ts` (pure helpers) and `handleNotificationAction` in `handlers.ts`; the API origin is baked in at build time from `VITE_API_URL` (already set for the web project), so no new variable.
- Retention prunes tokens one day after they expire; account export lists buttons (action and dates, never the token or hash); account delete removes them.

**Configure:** nothing new. Deploy the API first (the migration only adds a table), then the web (the new worker).

```bash
cd "$ROOT/apps/api" && source .venv/bin/activate
python manage.py migrate                                   # 0004_actiontoken
pytest modules/notifications modules/focus core -q && ruff check . && ruff format --check . && cd "$ROOT"
pnpm --filter @artha/web exec vitest run src/sw && pnpm check
```

**Roll back:** add `timer_buttons` to `NOTIFICATIONS_DISABLED_EVENTS` and redeploy the API: alerts go out without buttons and every tap is refused (the worker then shows "Open the app"). `notifications_send` at 0% or `NOTIFICATIONS_ENABLED=false` stops it too. To undo the code, revert the commit; the table can stay (retention empties it within a day).

Check what the buttons did with:

```sql
select action, count(*) filter (where used_at is not null) as used, count(*) as made,
       count(*) filter (where used_at is null and expires_at < now()) as expired_unused
from notifications_actiontoken where created_at > now() - interval '1 day' group by action;
select count(*) from notifications_actiontoken where expires_at < now() - interval '1 day';  -- 0 after the sweep's prune
```

**Check on a real Android phone** (Chrome, the app installed or in the browser, push on, flags on for you, a second device on iPhone or desktop if you have one):

1. Start a 1-minute custom round with overtime on, lock the phone. At the end the alert shows **Start break** and **Pause**; the iPhone or desktop alert shows no buttons.
2. Tap **Pause** within two minutes: the alert turns into "Timer paused" with **Resume**, the app does not open; open the app: the round is paused. Tap **Resume** in the notification: the round runs again.
3. Run another round, tap **Start break** at the end: "Break started", and the app shows the break running and the round saved in the tracker.
4. Replay: copy a token from the push (Chrome `chrome://inspect` > the worker > Console, `self.registration.getNotifications()` then `.data.tokens`) and post it twice; the second answer is `400 action_unavailable`:

   ```bash
   curl -s -X POST https://api.<your-domain>/api/v1/notifications/actions/ -H 'Content-Type: application/json' -d '{"token":"<token>"}'
   ```

5. Stale: let a round end, pause it in the app, then tap **Start break** on the alert: "Nothing changed", and the timer is still paused.
6. Late: let a round end with the phone locked and wait four minutes before tapping **Start break**: "Open the app"; open it and answer the question.
7. Break over (breaks start by themselves, next round does not): at the end of the break the alert shows **Start round 2**; tapping it starts round 2 with the same subject (when the app was not opened in between; otherwise without one).
8. Kill switch: set `NOTIFICATIONS_DISABLED_EVENTS=timer_buttons` on a preview deploy: the next alert has no buttons, and tapping an older one shows "Open the app".

**Decisions**

- Buttons: Start break and Pause on the overtime alert, Start break when the break waits, Start round N after a break, Resume on the paused confirmation (chosen with you). The PRD's "+5 min" is not offered because focus cannot extend a round that has reached its target; the `extend` action of the ERD was replaced by `start_focus`.
- Token lifetime 10 minutes (the ERD's value, confirmed with you). The version check makes any later change a no-op regardless.
- A tap counts as presence only within two minutes after the end, the same window as the heartbeat, so the button never credits a round that nobody saw end.
- The token is spent even when the tap then turns out to be stale or switched off; a token is never reusable.
- Tokens are shared by the student's Android devices for one alert: a tap on one phone spends it for the other.
- Only devices registered as `android` get buttons. Desktop Chrome supports them too, but the PRD scoped this to Android; widening it is one line (`domain/actions.PLATFORMS`).

### W3.7 Fatigue controls

Goal: a student who keeps ignoring alerts is offered fewer of them. After five unclicked pushes in a row over at least three days, the inbox and the notifications settings show "Fewer alerts, one daily digest?" once per 30 days. Accepting moves every category but the timer to the inbox and sends one digest a day at the student's nudge time. One migration (`0005_digest`), one endpoint (`GET`/`POST /api/v1/notifications/digest/`), no new environment variable. Also the P3 hardening of gate G3.

**What changed**

- The rule (`domain/fatigue.should_offer`, pure): the last five sent pushes that count towards the cap (so timer alerts and the test push are left out), one per notification however many devices got it (`selectors/fatigue.recent_pushes`, on `notif_delivery_sent_idx`); none clicked (a click from the notification or the inbox resets the run); on at least three different days in the student's own time zone; no offer in the last 30 days (`digest_offered_at`); not already on the digest.
- Offer: `GET digest/` answers `{offer, enabled, time}` and never writes. The card is shown in the inbox and in settings; as soon as it is shown the page posts `seen`, which records `digest_offered_at` (only when the offer is really due), so a reload does not bring it back. The card stays until answered. `decline` also records it.
- Accept (`services/digest.answer`): push off and inbox on for tracker, revision, plan, content, evaluation, exam and motivation (the timer keeps its push; the weekly summary keeps its email), `digest_enabled` on, `nudge_enabled` on and the slot planned. `stop` (the "Switch back to separate alerts" button in settings) turns the digest off and puts those push switches back to their defaults.
- The digest: new event `daily_digest` (catalogue category `digest`, outside the category grid, its switch is `digest_enabled`; priority 3, dedupe `digest:{local_date}`, expires after 6 hours). It rides the daily slot (`services/nudge`): for a student on the digest the slot sends the digest instead of the milestone, revision or thought push. It says, in this order, the exam milestone on its day, the chapters due for revision (both only when the student keeps that category in the inbox), and the unread inbox count, earlier digests not counted (`domain/digest`). It opens the inbox when something is unread, else revision, else home. A day with nothing to say sends nothing (logged `nudge_skipped reason=nothing_new`). Quiet hours, the cap, the master switch, `notifications_send` and `NOTIFICATIONS_DISABLED_EVENTS=daily_digest` apply as to any priority 3 push.
- Web: `DigestContainer` (offer card, outcome card that takes focus and speaks politely, and in settings the "Daily digest is on" card with the way back), `useDigest`, `getDigest`/`postDigestAnswer` with Zod, analytics `digest_offer_shown` and `digest_answered` (`place`, `answer`). Design-system tokens and icons only; the buttons wrap at 320 px.
- P3 hardening (`tests/test_p3_hardening.py`): every phase 3 push (stopwatch, goal, streak, nudge, revision, exam, content, digest) waits for the end of quiet hours, obeys its kill switch and the sending flag; a busy day of twenty alerts never goes past 3 counted pushes plus the one priority 1 slot; and on PostgreSQL the cap SQL below returns no rows.

**Configure:** nothing new.

```bash
cd "$ROOT/apps/api" && source .venv/bin/activate
python manage.py migrate                                   # 0005_digest
pytest modules/notifications -q && ruff check . && ruff format --check . && cd "$ROOT"
pnpm --filter @artha/web exec vitest run src/modules/notifications && pnpm check
```

**Roll back:** add `daily_digest` to `NOTIFICATIONS_DISABLED_EVENTS` to stop the digest pushes (students on the digest then only see the inbox and get timer alerts). The offer itself only shows with `notifications_ui`. To undo the code, revert the commit; the column can stay. Students already on the digest keep their push switches off until they switch back in settings (or run the reset SQL below).

Gate G3 (PRD 13.2) uses the SQL from W2.7 plus this cap check, which must return no rows:

```sql
select user_id, date_trunc('day', attempted_at at time zone 'Asia/Kolkata') as day, count(*)
from notifications_delivery
where status = 'sent' and counts_toward_cap and attempted_at > now() - interval '7 days'
group by 1, 2 having count(*) > 4;     -- cap is 3, plus one reserved slot for priority 1
```

Who is on the digest and who has been offered it:

```sql
select count(*) filter (where digest_enabled) as on_digest,
       count(*) filter (where digest_offered_at > now() - interval '30 days') as offered_30d
from notifications_settings;
```

**Check on real devices** (a student with a phone, push on, flags on for you; use your own uuid):

1. Force five ignored pushes over three days, then open the inbox: the offer card appears.

   ```sql
   update notifications_settings set digest_offered_at = null, digest_enabled = false where user_id = '<uuid>';
   insert into notifications_notification (id, user_id, category, event, dedupe_key, title, body, deep_link, tag, priority, context, created_at, updated_at)
   select gen_random_uuid(), '<uuid>', 'tracker', 'goal_reached', 'fatigue-test:' || g, 'Test', 'Test', '/app/tracker', '', 1, '{}', now() - (g || ' days')::interval, now()
   from generate_series(0, 4) g;
   insert into notifications_delivery (id, notification_id, user_id, channel, status, counts_toward_cap, attempt, attempted_at, sent_at, created_at, updated_at)
   select gen_random_uuid(), n.id, n.user_id, 'push', 'sent', true, 1, n.created_at, n.created_at, now(), now()
   from notifications_notification n where n.user_id = '<uuid>' and n.dedupe_key like 'fatigue-test:%';
   ```

2. Reload the inbox: the card is still there until you answer it; open settings in another tab: no second card (the offer was recorded).
3. Choose "Keep separate alerts": "No change". Nothing in the category grid moved. `digest_offered_at` is now set; the card does not come back.
4. Reset `digest_offered_at` to null, choose "Switch to a daily digest": in settings every category but Timer alerts has push off, and "Daily digest is on" shows your nudge time.
5. Force the slot: `update notifications_settings set next_nudge_at = now() where user_id = '<uuid>';` and run the sweep: one push "Your daily digest" naming the unread count; it opens the inbox. Run the sweep again: nothing more.
6. Start a 1-minute focus round: the timer alert still arrives at once.
7. "Switch back to separate alerts": the push switches are back on and the next nudge is the thought again.
8. Remove the test rows (deliveries first: the cascade lives in Django, not in the database):

   ```sql
   delete from notifications_delivery where notification_id in
     (select id from notifications_notification where user_id = '<uuid>' and dedupe_key like 'fatigue-test:%');
   delete from notifications_notification where user_id = '<uuid>' and dedupe_key like 'fatigue-test:%';
   ```
9. Check the card in Reading, Light, Dark and System at 320, 390, 768 and 1280 px: no horizontal scroll, buttons wrap, focus lands on the outcome card after answering.

Reset a student who should not have been switched (the same as "Switch back"):

```sql
update notifications_settings set digest_enabled = false where user_id = '<uuid>';
delete from notifications_preference where user_id = '<uuid>' and channel = 'push' and category <> 'timer' and enabled = false;
```

**Decisions**

- The digest is a daily push at the nudge time that takes the daily slot's place (chosen with you), not the weekly email. It is built from what the slot already knows (milestone, revision) plus the unread count, so a student on the digest still hears about their exam and revision once a day.
- Timer alerts are left out of the "unclicked" run (chosen with you): they are answered by acting on the timer, not by a click, and they never count towards the cap.
- "Over at least 3 days" means three different calendar days in the student's time zone among the five pushes.
- The offer counts as made when it is shown, not only when it is answered, so a student who ignores the card is not asked again for 30 days.
- Accepting forces the inbox on for those categories (a student who had hidden one gets it back in the inbox), and turns the daily nudge on, because the digest goes out in that slot. Switching back restores the push defaults rather than the exact earlier choices (the earlier choices are not stored).
- The digest has its own switch (`digest_enabled`) and is not a category in the grid; the master switch, quiet hours and the cap still apply to it.

Roll out each P3 wave through the same flag ladder as section 4 (steps 2 to 4 are enough: 5%, 25%, 100%).

## 6. Phase 4: floating timer (about 3 weeks, flag `floating_timer`)

Scope is PRD B (F-01.3) in the approved X-01 PRD: the pop-out (Document Picture-in-Picture), the `/app/focus/mini` fallback window, the start-of-round prompt, the install prompt (FR-C7) and the icon badge (FR-C8). FR-C9 (Android buttons) already shipped in W3.6. Waves and estimates: X-01.1 PRD section 13.1. Behaviour (controls per state, presence, prompt, alerts, theme): PRD B, sections "Behaviour per timer state" to "Alerts, sync and theme in the pop-out". Work on `main`, one pull request per wave.

| Wave | Scope | Days | Risk |
| --- | --- | --- | --- |
| W4.0 | Spikes S4.1 to S4.7 on real browsers | 2 | Finds the blockers early |
| W4.1 | `focus.0004_popout`, settings API and section, `phase_end_acknowledged` baseline | 2 | Low |
| W4.2 | Pop-out core: pill and card, controls per state, presence, one alert, theme | 5 | High (new browser API, background throttling) |
| W4.3 | Start-of-round prompt, pop out on Start | 2 | Low |
| W4.4 | `/app/focus/mini` fallback window | 1.5 | Medium (duplicate alerts across windows) |
| W4.5 | Install prompt, badge, G4 insight, device matrix | 2.5 | Low |

**Rules for every P4 wave**

- **No new timer logic.** Every control calls the existing `useFocusTimer` or `useStopwatch` actions with `version`. The server stays the only clock; the pop-out draws from `started_at`, `planned_seconds`, `paused_total_seconds` and the server clock offset.
- **One timer instance.** The pop-out is a React portal rendered by `LiveMiniTimer` (which owns the one `useFocusTimer` call for the corner), so it shares the query cache, the heartbeat and the alerts. The fallback window is a separate page and runs its own reads; W4.4 makes its chime and alerts play once.
- **Flag.** `floating_timer` is a web-only PostHog flag and fails open like `keep_awake` and `notifications_ui` (`useFeatureFlag` treats a missing flag as on). So **create it at 0% before W4.1 merges**. The API has no gate: the three settings columns are harmless, and the timer endpoints stay behind `focus_timer`. At 0% the Pop out buttons, the prompt, the settings section, the install offer and the badge disappear, and an open pop-out closes.
- **Roll back** any wave with the flag at 0% (about a minute, flag cache). The migration is additive and stays. No environment variable is added in P4 (section 8 unchanged).
- **Gate G4** (PRD 13.2) is read four weeks after the flag reaches 100%, from the insight built in W4.5.

Ladder for P4 (after W4.5 is signed off; earlier waves stay at "team only"): team, then 5% (hold 3 days), 25% (hold 3 days), 100%. Checks at each step: no new Sentry issue tagged `popout`; in PostHog, `popout_closed` with `seconds_open < 10` below 20% of opens (accidental opens), and the share of focus rounds answered "away" for students who had the pop-out open is not higher than for those who did not (the presence rule works).

### W4.0 Spikes (pop-out)

Goal: answer the browser questions that can sink W4.2 before any feature code. A throwaway page outside the repository (or a temp folder that is not committed), signed out, opened on `localhost` and on a Vercel preview over HTTPS. Results go into a new "P4" section of `docs/X-01-spike-results.md` (create the file if it does not exist yet), with browser, version, OS and pass or fail per row.

| Spike | Question | Pass when | If it fails |
| --- | --- | --- | --- |
| S4.1 Availability and React portal | Does `documentPictureInPicture.requestWindow({ width: 260, height: 72 })` open from a click on Chrome and Edge 116+ and Firefox 151+ (Windows and macOS)? Do clicks and keys in a React portal into the window reach their handlers? Does `pipWindow.resizeTo(320, 190)` from a click inside the window work? | Chrome and Edge pass all three on both OSes; Firefox result recorded | Chrome or Edge failing stops W4.2 (rethink); Firefox failing sends Firefox to the fallback window (W4.4); `resizeTo` failing means the size toggle closes and reopens the window at the new size |
| S4.2 Open from Start | Does the window open when `requestWindow` is called first thing in the Start click handler, before the start request is awaited? From a Space key press? | Opens from both on Chrome and Edge | Pop out on start works from clicks only; the Space shortcut starts the round without opening the window (noted in PRD FR-C5) |
| S4.3 Background throttling | With the window open, the opener tab hidden (another tab in front, then another app in front) for 15 minutes: does the clock tick every second when driven by `pipWindow.setInterval`, and does a 20 s fetch loop keep going? | Displayed time never more than 1 s off the server; no heartbeat gap above 25 s (network log) | Blocker for the presence rule: drive the heartbeat from the pop-out window's timers and retest; if still throttled, take the presence rule back to the owner |
| S4.4 Wake lock in the pop-out | Does `pipWindow.navigator.wakeLock.request('screen')` keep the display on with the opener hidden and another app in front (display sleep set to 1 minute)? | Display stays on 5 minutes on Chrome and Edge, Windows and macOS | Nothing is built; PRD C row stays "companion only" |
| S4.5 Theming | Do cloned `<link rel="stylesheet">` and `<style>` nodes plus the copied `data-theme`, `class` and `color-scheme` render all four themes? Does a switch in the main tab show in the window within 1 s? Do the fonts load? | Screenshots of pill and card in Reading, Light, Dark and System (day and night) attached; switch follows | Inline the token stylesheet into the window instead of cloning links, then retest |
| S4.6 Back to the opener | Does `window.focus()` on the opener, called from a click in the window, bring the Artha tab forward? | Works on Chrome and Edge | "Back to Artha" is hidden; the browser's own back-to-tab control is the way back |
| S4.7 Safari video trick | Can a canvas drawn every second, captured to a `<video>` and sent to Picture-in-Picture, show a readable timer on Safari 18 (macOS)? Does `window.open(..., 'popup,width=320,height=220')` honour the size on Safari? | Go or no-go recorded; nothing is promised or built in P4 | Go becomes a backlog item, not a P4 wave |

```bash
cd "$ROOT"
pgrep -x git >/dev/null || find .git -maxdepth 3 -name "*.lock" -print -delete
git --no-optional-locks status --short          # must be empty: spikes are not committed
```

Feature detection to paste into the console of any browser:

```js
;({ pip: 'documentPictureInPicture' in window, wakeLock: 'wakeLock' in navigator, badge: 'setAppBadge' in navigator, installEvent: 'onbeforeinstallprompt' in window })
```

**Results (2026-10-07, Chrome on macOS, Safari for S4.7; details in `docs/X-01-spike-results.md`):** Chrome enforces a minimum window of about 320x156 (260x72 is not possible; `resizeTo(320,190)` changed nothing at that size); clicks and keys reach a React portal; open-first works from click and Space and fails after 8 s; `window.focus()` returns to the tab; theme clone follows in 7 ms; Safari video trick and `window.open` popup work in Safari (Chrome opens a tab). Still to verify on the W4.2 build: 15 minute hidden run (S4.3), wake lock from the pop-out (S4.4), Edge, Firefox 151+, Windows, `resizeTo` above the minimum.

**Decisions:** spikes run on the team's own machines (Windows and macOS, one second monitor); a failure in Firefox alone never blocks P4, because Firefox users get the fallback window.

### W4.1 Settings and baseline (api and web)

Goal: the three pop-out settings exist on the account, the student can set them (behind the flag), and the "gap after a round ends" is measured before any pop-out reaches students, so FR success measure "lower than today" has a baseline.

**What changes**

- API: `focus_focussettings` gains `popout_on_start` (default false), `popout_size` (`pill` or `card`, default `pill`, check constraint `focus_settings_popout_size_valid`) and `popout_prompt_seen` (default false), migration `focus.0004_popout` (ERD 2.9). `SettingsSerializer` gets two booleans and `popout_size = ChoiceField(["pill", "card"])`; `services.update_settings` adds the two booleans to its list of switch keys and handles `popout_size`; `selectors.settings_dict` returns all three, so they also arrive in `state.settings` of `GET /focus/timer/`. Export carries them through the generic field dump; the eraser deletes the row as today.
- Web: `FocusSettings` type, a "Pop-out" section in `FocusSettingsForm` on `/app/settings/focus` with "Pop out when I start a round" and "Size: Pill or Card". The section shows only with `floating_timer` on; on a browser without Document Picture-in-Picture it adds one line: "Your browser opens a small separate window instead, which does not stay on top."
- Detection: `focus/lib/pip.ts` holds `isDocumentPipSupported()` (the settings note uses it; W4.2 adds the window code to the same file).
- Baseline: pure helpers in `focus/lib/timer-math.ts`: `phaseEndMs`, `nextPendingEnd` (which ended phase is still unanswered: a timer past its end or away becomes pending, a different running timer drops it, idle keeps it) and `phaseEndGap(endAtMs, actionAtMs)` (whole seconds, capped at 7200, null when the action came before the end). `useFocusTimer` sends `phase_end_acknowledged` (`seconds`, `surface: "tab"`, `phase`) once per phase end, on the first of: Stop and save in overtime, Start break, Skip break, Start round, the away claim. This event is not behind `floating_timer`.

**Configure:** create the PostHog flag `floating_timer` at 0% now. No environment variable.

```bash
cd "$ROOT"
pgrep -x git >/dev/null || find .git -maxdepth 3 -name "*.lock" -print -delete
cd apps/api && source .venv/bin/activate
python manage.py makemigrations focus -n popout            # creates 0004_popout; then edit nothing by hand
python manage.py makemigrations --check --dry-run          # must say: No changes detected
python manage.py migrate
pytest modules/focus -q && ruff check . && ruff format --check . && cd "$ROOT"
pnpm --filter @artha/web exec vitest run src/modules/focus && pnpm check
```

Production migration first (the API deploy runs it; three columns with defaults are metadata-only, the check constraint scans a small table once), then the web.

**SQL check** (Supabase SQL editor, after deploy):

```sql
select popout_size, popout_on_start, popout_prompt_seen, count(*) from focus_focussettings group by 1, 2, 3;
select conname from pg_constraint where conname = 'focus_settings_popout_size_valid';   -- one row
```

**Tests:** serializer accepts `pill` and `card` and answers 400 for `big`; `update_settings` reports the changed names; a new row has the three defaults; the check constraint rejects a raw `update ... set popout_size = 'big'`; `export_all` includes the fields; erase leaves no row. Web: the form section hides with the flag off, saves both fields, keyboard and four themes; `phaseEndGap` edge cases (before end, exactly at end, over the cap).

**Check on real devices:** with the flag on for you, change both settings on a laptop and reload on a phone: the values follow the account. With the flag at 0%: no section. Finish a round in the tab and act on it: one `phase_end_acknowledged` in PostHog with `surface = tab`.

**Roll back:** flag at 0% hides the section; the baseline event keeps flowing (it changes nothing for the student). The columns stay.

**Decisions:** the size is remembered on the account (ERD column), not per device; `popout_prompt_seen` is written when the prompt is shown (W4.3); the baseline event ships before the pop-out so the comparison is honest.

### W4.2 Pop-out core (web)

Goal: on Chrome, Edge and Firefox 151+ on desktop, one click on Pop out opens a small always-on-top window with the live timer and the controls of the focus page, in sync within one second, in all four themes, without a second source of truth.

**What changes**

- Design system: three Lucide icons added to `packages/design-system/src/icons.ts`: `PictureInPicture2` (Pop out), `Minimize2` and `Maximize2` (size toggle).
- `focus/lib/popout.ts` (pure): `popoutView(timer, idle, stopwatch, nowMs, lastContext)` returns the kind, the clock text, the spoken text ("24 minutes 12 seconds left") and the controls for each state in PRD B "Behaviour per timer state"; `popoutAlive({ tabVisible, recentlyActive, popoutOpen, pastTarget, tappedSinceTarget })` is the presence rule (PRD B "Presence while the pop-out is open"); `POPOUT_SIZES = { pill: [320, 156], card: [320, 300] }` (Chrome will not open smaller than about 320x156; the pill is the compact layout).
- `focus/lib/pip.ts`: support check, `copyStyles(from, to)` (clones every stylesheet link and style node), `mirrorTheme(fromRoot, toRoot)` (copies `data-theme`, `class`, `color-scheme`, then a `MutationObserver` keeps them in step), and the window title "Artha timer" (the window's accessible name).
- `useDocumentPip()`: `open(size)` (must be called inside a click), `close()`, `resize(size)` (from a click inside the window: tries `resizeTo`, verifies the new size and, if it did not change, only the layout switches; the window never closes and reopens, because reopening needs a click in the opener), the window's `pagehide` closes the state, and a `presence` source the timer read uses.
- `MiniTimerView` gets a `variant` (`corner`, `pill`, `card`); the corner keeps its fixed placement, the other two fill the window. Layout follows the window width and height (container queries), so a window the browser makes bigger or smaller still works. The card adds `TimerRing`. One timer UI, as the PRD asks.
- `LiveMiniTimer`: `FocusMini` keeps its `useFocusTimer` call mounted while the flag is on (the corner still hides when nothing runs), and renders `PopOutTimer`, a portal into the window. The stopwatch shows in the same window when it is the live timer.
- Pop out buttons (40 px, icon with an accessible name "Pop out the timer"): on the corner mini timer, and on the focus card next to the controls. Both hidden when the flag is off or the window is already open (then "Bring back" closes it).
- Sync: while the window is open, `useTick` and the heartbeat run on the window's own timers (`pipWindow.setInterval`) and the timer query polls in the background (`refetchIntervalInBackground`), per S4.3. `fetchTimerState` reads presence through `popoutAlive`.
- Alerts: no browser notification from the pop-out; the round-end state is drawn in the phase-end colour with one large button, announced once in a polite live region inside the window. The chime plays from the one `useFocusAlerts` instance, so once.
- Keep awake: S4.4 showed the main tab's lock is released when the tab is hidden, so `useKeepAwake` accepts a target window and requests the lock from the pop-out document while it is open (the `keepawake` module, through its barrel).
- Closing the window never stops the timer. Closing the Artha tab closes it (browser rule); the push still arrives.
- Analytics: `popout_opened` (`supported: "pip"`, `size`, `source: mini | focus_page`, `timer`), `popout_closed`, `popout_size_changed`, `popout_session`, `phase_end_acknowledged` with `surface: "popout"` when the action came from the window.

**Configure:** nothing new. Flag stays at "team only".

```bash
cd "$ROOT"
pgrep -x git >/dev/null || find .git -maxdepth 3 -name "*.lock" -print -delete
pnpm --filter @artha/web exec vitest run src/modules/focus src/modules/keepawake && pnpm check
pnpm build:web && pnpm --filter @artha/web start           # http://localhost:3000, sign in, start a round
```

**Tests:** `popoutView` for every row of the state table (before target with extensions left and none left, overtime with breaks on and off, paused, away, each break, phase waiting, idle with and without a remembered subject, stopwatch running and paused); `popoutAlive` across the target (before, after with and without a tap, tap after two minutes); size memory (toggle writes `popout_size`); `useDocumentPip` with a mocked `documentPictureInPicture` (open, `pagehide`, resize fallback, unsupported); `PopOutTimer` renders into the mocked window, clicks reach the actions, the flag turning off closes the window; `MiniTimerView` variants keep 40 px targets.

**Check on real devices** (Chrome, Edge and Firefox 151+, on Windows and macOS; a second monitor on one of them). These also close the open spikes: add a step 12 for S4.3 (15 minutes with the tab hidden, no gap above 25 s in the network log) and a step 13 for S4.4 (display stays on 5 minutes with the opener hidden):

1. Start a 5-minute round on `/app/focus`, click Pop out on the focus card: a pill opens with the clock and Pause. Switch to a PDF in another app: the pill stays on top.
2. Pause in the pill: the main tab shows paused within one second. Resume from the main tab: the pill follows within one second.
3. Toggle to the card (320x300, or layout only if the browser keeps the size): ring, subject and chapter, Pause, +5 (3 left), End. Press +5 twice: "(1 left)". Close and reopen: it opens as a card.
4. Let the round reach its target with overtime on: the window turns to the phase-end colour, "+00:05", one large Start break; the chime plays once; at most one OS alert. +5 is not offered. Tap Start break: the break runs in the window and the round is saved in the tracker.
5. Presence: run a round with the main tab hidden and do not touch anything for the whole round, then do not tap for 3 minutes after the target. The round is counted (not "away"), closed at its target, no overtime. Repeat and tap within two minutes: overtime keeps counting.
6. Close the main tab: the window closes; the push for the round end still arrives.
7. Drag the window to the second monitor, reopen: the browser places it (we do not control position).
8. Theme: switch Reading, Light, Dark and System in the main tab: the window follows within a second. Check contrast of the clock, the button labels and the focus ring at pill size in all four. Reduced motion on in the OS: no tick animation in the ring.
9. Keyboard only: Tab into the window, the focus ring is visible on every control, Enter and Space act; a screen reader reads "Artha timer" and "24 minutes 12 seconds left", and the round-end message once.
10. Stopwatch: start it on `/app/tracker`, pop out from the corner timer: elapsed time and Pause or Resume.
11. Flag at 0% while the window is open: it closes; no Pop out button anywhere.

**Roll back:** flag `floating_timer` at 0%.

**Decisions:** Compact 320x156 and Card 320x300 after S4.1; the size toggle never closes the window; controls mirror the focus page (D8); presence counts until the target and after a tap (D9); the window is a portal of the existing tree, not a separate render, so it shares the cache and the alerts; the window position is the browser's choice; End in the window does not ask for a reason.

### W4.3 Start-of-round prompt and pop out on Start (web)

Goal: students discover the pop-out at the moment it helps, once, and can make it automatic.

**What changes**

- `focus/lib/popout.ts`: `promptEligible({ supported, desktop, flagOn, popoutPromptSeen, popoutOnStart, phase, popoutOpen })`: true only on a desktop browser with Document Picture-in-Picture, the flag on, the prompt never seen, the setting off, a focus round (not a break) and no window open.
- `PopOutPromptCard` (presentational): inline under the focus card, "Keep the timer on top while you study?", Pop out (primary), Not now, and a checkbox "Do this every time I start a round". Not a modal; focus does not move to it; announced politely once.
- When it shows, the page writes `popout_prompt_seen = true` (the same "counts when shown" rule as the digest offer). Pop out opens the window (the click) and, with the box ticked, writes `popout_on_start = true`.
- Pop out on start: every Start handler (focus card button, the Space shortcut if S4.2 passed, Start round N in the window) calls `open(size)` before it sends the start request, when `popout_on_start` is on, the browser supports it and no window is open.
- Analytics: `popout_prompt_shown`, `popout_prompt_answered` (`answer`, `always`), `popout_opened` with `source: prompt | auto_start`.

**Configure:** nothing new.

```bash
cd "$ROOT"
pgrep -x git >/dev/null || find .git -maxdepth 3 -name "*.lock" -print -delete
pnpm --filter @artha/web exec vitest run src/modules/focus && pnpm check
```

**SQL check** (how many students saw the prompt and turned on the setting):

```sql
select count(*) filter (where popout_prompt_seen) as prompt_seen,
       count(*) filter (where popout_on_start) as on_start
from focus_focussettings;
-- reset yourself to see the prompt again:
update focus_focussettings set popout_prompt_seen = false, popout_on_start = false where user_id = '<uuid>';
```

**Tests:** `promptEligible` for each condition; the card writes `popout_prompt_seen` once when shown; Pop out with the box ticked writes `popout_on_start`; with the setting on, a mocked `requestWindow` is called inside the Start click before the request; Safari (no API) never shows the card.

**Check on real devices:** reset with the SQL above. Chrome: start a round, the card appears, reload: it does not come back. Reset, tick the box and Pop out: the window opens; next round, pressing Start opens it with no prompt. Safari: no card. Phone: no card. Keyboard: the card's buttons reachable, four themes at 320 px (buttons wrap).

**Roll back:** flag at 0%; students who turned the setting on keep it, but nothing opens while the flag is off.

**Decisions:** once ever per student, recorded when shown, setting default off (D11); not offered where only the fallback window exists, because that window does not stay on top.

### W4.4 Fallback window `/app/focus/mini` (web)

Goal: Safari and Firefox below 151 get a small separate window with the same timer, honestly labelled as not always on top.

**What changes**

- Route `app.focus.mini.tsx` (URL `/app/focus/mini`, `buildHead` with `noindex`, `staticData: { chrome: 'bare' }`). `SiteShell` drops the header and footer for a bare route; the corner `LiveMiniTimer` and the bell are not drawn there. `LastVisitReporter` ignores the route so "last visit restore" never lands a student in it.
- `MiniWindowContainer`: the same `PopOutTimer` view filling the window, pill below 300 px wide, card above. It runs its own `useFocusTimer` (it is its own page). A one-line note at the first open: "This window does not stay on top in this browser."
- Pop out on a browser without Document Picture-in-Picture calls `window.open('/app/focus/mini', 'artha-timer', 'popup,width=320,height=220')` from the click; a second click focuses the same named window.
- One chime and one alert per phase end across windows: before playing, `useFocusAlerts` claims `artha:alerted:<client_id>:<version>` in `localStorage` (shared by same-origin windows, wrapped in try and catch); only the first window plays. A local notification is skipped when any Artha window is visible. The push keeps its shared tag.
- Presence: the fallback window uses the same rule as the pop-out (`popoutAlive`), judged by its own visibility. Because it is not on top, it often is hidden behind the PDF; then the round end follows the normal away rules, and the window says so in its note.
- Analytics: `popout_opened` with `supported: "window"`, `phase_end_acknowledged` with `surface: "mini_window"`.

**Configure:** nothing new.

```bash
cd "$ROOT"
pgrep -x git >/dev/null || find .git -maxdepth 3 -name "*.lock" -print -delete
pnpm --filter @artha/web exec vitest run src/modules/focus src/modules/layout src/modules/personalization && pnpm check
pnpm build:web && grep -o '"/app/focus/mini"' apps/web/src/routeTree.gen.ts   # the generated tree has the route (commit it)
```

**Tests:** the route renders without the site header, has `noindex`, is skipped by the last-visit reporter; pill and card by width; with two windows mocked on one `localStorage`, the chime plays once; the note shows once.

**Check on real devices:** Safari 18 on macOS and Firefox below 151 (or Firefox with the API turned off in `about:config`): Pop out opens a small window at about 320 by 220 (if Safari opens a tab instead, record it), controls work, the main tab follows within a second, round end plays one chime with both windows open, close the main tab: the small window keeps working (it is its own page) and becomes the one that chimes. Four themes, 320 px, keyboard.

**Roll back:** flag at 0% (the route then redirects to `/app/focus`).

**Decisions:** a separate page, not a portal, because `window.open` windows survive the opener and cannot share its React tree safely; the chime claim lives in `localStorage` because it is a per-device convenience, not shared state.

### W4.5 Install prompt, badge and gate G4 (web)

Goal: FR-C7 and FR-C8 (approved to stay in P4, D10), the G4 insight, and the P4 device matrix before the flag climbs.

**What changes**

- `notifications` module (it owns environment detection, `lib/platform.ts`, and the iPhone install steps): `useInstallPrompt` captures `beforeinstallprompt` at boot in `NotificationsBoot` (the event fires early) and `appinstalled`; `InstallOfferCard` shows on `/app/focus` after the student's second completed focus round on this device (a device counter in `localStorage`), at most once per 30 days (timestamp in `localStorage`), never in the installed app (`display_mode = standalone`), never in an in-app browser. Chrome and Edge: "Install Artha" calls `prompt()`. iPhone and iPad Safari: the install steps of `InstallGuide`, extracted into a shared presentational piece so the alerts step and this card use one copy. Safari on macOS: one line, "File, Add to Dock". Exported through the `notifications` barrel; `focus` imports only the barrel.
- `display_mode` is registered as a PostHog super property at boot, so every event (including `focus_session_started`) carries it for G4.
- Badge: `focus/lib/appBadge.ts` sets `navigator.setAppBadge()` (a dot, no number) while a focus round, break or stopwatch runs and clears it when idle, on sign-out and when the flag is off. Feature-detected; a stale dot after the tab closed mid-round clears on the next open (accepted).
- Analytics: `pwa_install_result` (`accepted`, `dismissed`, `guide_shown`, `installed`).
- PostHog insight **"G4 floating timer reach"** (Trends, unique users, last 28 days, filter `$device_type = Desktop`): series A `focus_session_started`; series B `popout_opened`; series C `focus_session_started` where `display_mode = standalone`; formula `(B + C) / A` (an upper bound if a student does both; for the exact figure, a cohort "opened pop-out or used installed app" divided by A). Pin it to the X-01 dashboard with the date the flag reached 100%.

**Configure:** nothing new.

```bash
cd "$ROOT"
pgrep -x git >/dev/null || find .git -maxdepth 3 -name "*.lock" -print -delete
pnpm --filter @artha/web exec vitest run src/modules/notifications src/modules/focus && pnpm check
```

**Tests:** offer eligibility (round count, 30 days, standalone, in-app browser, unsupported); the prompt result is reported once; the shared install steps render in both places; badge set and cleared by state with a mocked `navigator`.

**Check on real devices (P4 matrix, sign off in `docs/X-01-spike-results.md`):**

1. Chrome and Edge on Windows: finish two rounds, the offer appears; install; the app opens in its own window; the taskbar icon shows a dot while a round runs and loses it at the end. The offer never shows inside the installed app.
2. Chrome on macOS: same, dock icon dot.
3. Android Chrome: the offer after two rounds; install; the W3.6 buttons still work.
4. iPhone Safari: the card shows the install steps; after install, no card.
5. Firefox 151+, Safari on macOS: pop-out or fallback per W4.2 and W4.4; no install button where the browser has none.
6. All of W4.2 checks 8 and 9 (four themes at 320 px and at pill size, keyboard, screen reader, reduced motion) once more on the final build.

**Roll back:** flag at 0% hides the offer and stops the badge (cleared on the next state change).

**Decisions:** install prompt and badge stay in P4 because G4 counts the installed app (D10); the device counter and the 30-day memory are per device in `localStorage`, because installing is per device; the badge is a dot, never a count.

## 7. Phase 5: desktop companion (only if gate G4 passes)

Gate G4 (approved PRD): four weeks after P4, at least 25% of desktop focus students use the pop-out or the installed app, and feedback asks for "works when my browser is closed" or system-wide keep awake. If not met, stop here.

The approved-for-review build document is `docs/X-01-P5-DESKTOP-COMPANION.md` (gate G4 met 2026-10-07; no code until it is approved).

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
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_USE_TLS`, `EMAIL_BACKEND`, `EMAIL_TIMEOUT`, `NOTIFICATIONS_EMAIL_FROM` | | yes | no | P3 (W3.5) |
| `EMAIL_HOST_PASSWORD` | | yes | yes | P3 (W3.5) |

P4 (floating timer) adds no variable. Rule from `SETUP.md` stays: nothing secret gets a `VITE_` prefix.

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
