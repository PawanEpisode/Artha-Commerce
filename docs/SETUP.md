# Setup guide: exactly what to do on each platform

Do these in order. Total time: about 60 to 90 minutes. Copy values into a password manager as you go.

You will end with **two Vercel projects** (web, api) from **one GitHub repo**, backed by **one Supabase project**.

---

## 0. Prerequisites on your Mac

```bash
node -v          # 22 or newer
corepack enable  # gives you pnpm
pnpm -v
python3 --version  # 3.12 recommended
```

Open the project folder and install:

```bash
cd ~/Desktop/personal-work/ArthaCommerce
pnpm install     # installs dependencies and the git hooks (Husky)
cp apps/web/.env.example apps/web/.env.local
cp apps/api/.env.example apps/api/.env
```

---

## 1. GitHub

1. github.com -> **New repository**. Name `arthacommerce`, **Private**, no README/gitignore (we have them).
2. In the project folder:
   ```bash
   git init -b main        # skip if already initialised
   git add -A && git commit -m "chore: initial foundation"
   git remote add origin git@github.com:<you>/arthacommerce.git
   git push -u origin main
   ```
3. Repo **Settings -> Branches -> Add rule** for `main`: require a pull request and require the **CI** checks (`web`, `api`) to pass.
4. Workflow work from now on: branch -> PR -> CI green -> merge. Vercel creates a preview URL for every PR.

---

## 2. Supabase (Pro plan)

### 2.1 Project
1. supabase.com/dashboard -> **New project**. Region: **Mumbai (ap-south-1)** for Indian students. Save the database password.

### 2.2 Collect keys
- **Project Settings -> API** (or the **Connect** button): copy
  - Project URL -> `SUPABASE_URL` (api) and `VITE_SUPABASE_URL` (web)
  - **Publishable / anon key** -> `VITE_SUPABASE_ANON_KEY` (web). Safe for the browser.
  - **Service role / secret key** -> `SUPABASE_SERVICE_ROLE_KEY` (api only, Vercel API project, secret). F-16 needs it to delete a student's account and avatar files. Never give it a `VITE_` prefix and never put it in the web project.
- **Connect -> Connection string**:
  - **Transaction pooler** (port **6543**) -> `DATABASE_URL` (api runtime)
  - **Session pooler** or **Direct** (port **5432**) -> `DIRECT_DATABASE_URL` (api migrations)
  - Replace `[YOUR-PASSWORD]` in both.
- **Project Settings -> JWT Keys**: new projects use asymmetric signing keys and the API reads them automatically from `SUPABASE_URL`. Only if your project still shows a **legacy JWT secret** in use, copy it to `SUPABASE_JWT_SECRET` (api).

### 2.3 Authentication

The app supports: **Google**, **email code (6 digits) or magic link**, **email + password**, **forgot / reset password**, **invite**, **change email** and **reauthentication** for sensitive changes. These map one to one to the six templates under **Authentication -> Emails -> Templates**.

1. **Authentication -> Sign In / Providers -> Email**: enable it, then set:
   - **Confirm email**: ON (students must prove they own the address)
   - **Secure email change**: ON (confirmation goes to the old and the new address)
   - **Secure password change**: ON (changing a password needs a recent sign-in or the emailed code)
   - **Minimum password length**: 8, **Password requirements**: letters and digits
   - **Email OTP length**: 6, **Email OTP expiration**: 3600 seconds (the templates say 60 minutes)
2. **Google provider**:
   - console.cloud.google.com -> create/select a project -> **APIs & Services -> OAuth consent screen** (External, add your email and app name).
   - **Credentials -> Create credentials -> OAuth client ID -> Web application**.
   - Authorised redirect URI: `https://<your-project-ref>.supabase.co/auth/v1/callback` (shown in the Supabase Google provider panel).
   - Paste the Client ID and Secret into Supabase **Google** provider and enable it.
3. **Authentication -> URL Configuration**:
   - **Site URL**: your production web URL (use `http://localhost:3000` until you have one). The email links are built from it.
   - **Redirect URLs** (add all; use the same three paths for each origin):
     - `http://localhost:3000/auth/callback`, `/auth/confirm`, `/auth/reset-password`
     - `https://<your-prod-domain>/auth/callback`, `/auth/confirm`, `/auth/reset-password`
     - `https://*-<your-vercel-team-slug>.vercel.app/**` (preview deployments)
4. **Email templates** (**Authentication -> Emails -> Templates**, the screen with Confirm sign up, Invite user, Magic link or OTP, Change email address, Reset password, Reauthentication).
   The branded HTML lives in the repo and is generated from one layout (`packages/email-templates`). Pick one way:

   **A. Paste in the dashboard** (no tools needed). For each row open the template, set the **Subject** and paste the file contents into **Message body**, then **Save**:

   | Dashboard template | Subject | File to paste |
   | --- | --- | --- |
   | Confirm sign up | Confirm your ArthaCommerce account | `supabase/templates/confirm-signup.html` |
   | Invite user | You have been invited to ArthaCommerce | `supabase/templates/invite-user.html` |
   | Magic link or OTP | Your ArthaCommerce sign-in link and code | `supabase/templates/magic-link.html` |
   | Change email address | Confirm your new ArthaCommerce email address | `supabase/templates/change-email.html` |
   | Reset password | Reset your ArthaCommerce password | `supabase/templates/reset-password.html` |
   | Reauthentication | Your ArthaCommerce verification code | `supabase/templates/reauthentication.html` |

   **B. Push with the Supabase CLI** (keeps dashboard and repo in sync):
   ```bash
   brew install supabase/tap/supabase
   supabase login
   supabase link --project-ref <your-project-ref>
   supabase config push        # shows a diff first. Review, then confirm. Google and SMTP stay in the dashboard.
   ```
   Regenerate the HTML after any wording or colour change with `pnpm emails:build` (CI fails if the committed files are stale).
5. **Invite user** (admins and editors): **Authentication -> Users -> Invite user**. The person gets the Invite email, taps the button, lands on `/auth/confirm` and then on **Set your password**.
6. **Test every flow** (use a Gmail and an Outlook address): sign up -> confirm by link and by code; sign in with email code; forgot password -> reset; change email in **/app/account** -> confirm both emails; change password in **/app/account** (you may be asked for the emailed code).

### 2.3.1 Email delivery (SMTP)
Supabase's built-in sender only emails your own team and is limited to a few emails per hour. Before inviting real students, set up your own SMTP in **Authentication -> Emails -> SMTP Settings** and switch **Enable custom SMTP** on.

| Field | Value |
| --- | --- |
| Sender email | `no-reply@mail.<your-domain>` (a subdomain keeps your main domain reputation clean) |
| Sender name | ArthaCommerce |
| Host / Port | from your provider (table below). Port 465 uses TLS, 587 uses STARTTLS |
| Username / Password | from your provider |
| Minimum interval between emails | 60 seconds |

| Provider | Host | Notes |
| --- | --- | --- |
| Resend | `smtp.resend.com` | username `resend`, password is an API key. Simplest start |
| Amazon SES (Mumbai) | `email-smtp.ap-south-1.amazonaws.com` | cheapest at scale; create SMTP credentials, verify the domain, request production access |
| Brevo | `smtp-relay.brevo.com` | port 587, SMTP key as password, generous free tier |

DNS records at your domain provider (your email provider shows the exact values): **SPF**, **DKIM**, and a **DMARC** record (`v=DMARC1; p=none; rua=mailto:you@<your-domain>` to start). Gmail and Yahoo reject or spam-folder bulk mail without them. After setup send yourself a sign-in code and confirm it lands in the inbox, not spam.

### 2.4 Lock down the Data API (important)
All app data is read and written by Django, so the browser must never reach tables directly.
- **Project Settings -> API / Data API**: **disable the Data API** (or remove `public` from exposed schemas).
- Django also enables Row Level Security on every public table after each migration, as a second layer.

### 2.5 Create the tables
From your Mac, run Django migrations against the **direct** connection:

```bash
cd apps/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DJANGO_DEBUG=true
export DIRECT_DATABASE_URL='postgresql://postgres.<ref>:<password>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres'
python manage.py migrate
```

Check **Table Editor**: you should see `profiles` (RLS enabled).

### 2.6 Avatar bucket (F-16)
Student avatars live in one **public** Storage bucket with random object keys (`<user id>/<random>.webp`), so the URL is not guessable and the CDN can cache it. Only the API writes to it, with the service role key.
- **Storage -> New bucket**: name `avatars`, **Public bucket on**, file size limit 1 MB, allowed types `image/webp`. (Or run `supabase config push`: the bucket is declared in `supabase/config.toml`.)
- Set `SUPABASE_AVATAR_BUCKET=avatars` on the API project if you use another name.
- Add **no** Storage policies: uploads and deletes happen only through the API.

---

## 3. Google AI Studio (Gemini)

1. aistudio.google.com/apikey -> **Create API key** (in a new or existing Google Cloud project).
2. Copy it to `GEMINI_API_KEY`. It goes **only** in the **api** Vercel project, never the web project.
3. Optional: set `GEMINI_MODEL` (default `gemini-flash-latest`).

---

## 4. Sentry

1. sentry.io -> create an organisation (or use yours).
2. **Create two projects**:
   - Platform **React** named `artha-web` -> copy its **DSN** -> `VITE_SENTRY_DSN` (web)
   - Platform **Django** named `artha-api` -> copy its **DSN** -> `SENTRY_DSN` (api)
3. **Source maps (web)**: Settings -> **Developer Settings -> Organization Tokens -> Create** token. Then in the web Vercel project set:
   - `SENTRY_AUTH_TOKEN` = the token
   - `SENTRY_ORG` = your org slug
   - `SENTRY_PROJECT` = `artha-web`
   Builds then upload source maps automatically.
4. Optional: Sentry -> **Alerts** -> email/Slack on new issues.

---

## 5. PostHog

1. posthog.com -> create a project. Pick **US Cloud** (the repo proxy is set up for US).
   - If you pick **EU**, edit `apps/web/vercel.json` and replace `us.i.posthog.com` -> `eu.i.posthog.com`, `us-assets.i.posthog.com` -> `eu-assets.i.posthog.com`, and set `VITE_POSTHOG_UI_HOST=https://eu.posthog.com`.
2. **Project settings** -> copy the **Project API key** (`phc_...`) -> `VITE_POSTHOG_KEY` (web).
3. Leave `VITE_POSTHOG_HOST=/ingest`. Traffic goes through your own domain so ad blockers do not drop events.

---

## 6. Vercel: API project (do this first)

1. vercel.com -> **Add New -> Project** -> import the GitHub repo.
2. **Project name**: `arthacommerce-api`.
3. **Root Directory**: `apps/api`. **Framework Preset**: **Other**. Leave build/output blank.
4. **Environment Variables** (Production and Preview):

   | Name | Value |
   | --- | --- |
   | `DJANGO_SECRET_KEY` | long random string: `python3 -c "import secrets;print(secrets.token_urlsafe(64))"` |
   | `DJANGO_DEBUG` | `false` |
   | `DJANGO_ALLOWED_HOSTS` | your API domain, e.g. `api.yourdomain.com` (`.vercel.app` is always allowed) |
   | `CORS_ALLOWED_ORIGINS` | your web origins, comma separated, e.g. `https://yourdomain.com,https://www.yourdomain.com` (add preview origins if you need them) |
   | `DJANGO_ADMIN_PATH` | secret-ish path for the content admin, e.g. `studio-x7k2` (default `admin`). Staff open `https://<api>/<this>/` |
   | `CSRF_TRUSTED_ORIGINS` | your API origin, e.g. `https://api.yourdomain.com` (needed for admin login over HTTPS) |
   | `DATABASE_URL` | Supabase **transaction pooler** string (port 6543) |
   | `DIRECT_DATABASE_URL` | Supabase direct/session string (port 5432) |
   | `SUPABASE_URL` | `https://<ref>.supabase.co` |
   | `SUPABASE_JWT_SECRET` | only if your project uses the legacy HS256 secret |
   | `GEMINI_API_KEY` | from AI Studio |
   | `GEMINI_MODEL` | optional |
   | `SENTRY_DSN` | `artha-api` DSN |

5. **Deploy**. Then open `https://<api-url>/api/v1/health/ready/`. Expect `{"status":"ok","database":"up"}`.
6. **Settings -> Domains**: add `api.yourdomain.com` and follow the DNS instructions.

> Vercel Python reads `apps/api/requirements.txt` and `.python-version` (3.12). It serves `config/wsgi.py`. Do not rewrite every path to `/api/index`: that makes `/admin/` and `/api/v1/` both 404.

---

## 7. Vercel: Web project

1. **Add New -> Project** -> same GitHub repo.
2. **Project name**: `arthacommerce-web`.
3. **Root Directory**: `apps/web`. Keep **Include source files outside of the Root Directory** enabled.
4. Framework is taken from `apps/web/vercel.json` (`tanstack-start`). Install command default (`pnpm install`) works with the root workspace.
5. **Environment Variables** (Production and Preview):

   | Name | Value |
   | --- | --- |
   | `VITE_SITE_URL` | `https://yourdomain.com` (**origin only: scheme + host, NO path, NO trailing slash**. Drives canonical, `og:url`, `og:image`, sitemap and robots, so it decides whether WhatsApp shows a preview. A path such as `/login` breaks every link preview; the app strips it, but fix the variable anyway) |
   | `VITE_SITE_NAME` | `ArthaCommerce` |
   | `VITE_SUPABASE_URL` | Supabase project URL |
   | `VITE_SUPABASE_ANON_KEY` | Supabase publishable/anon key |
   | `VITE_API_URL` | `https://api.yourdomain.com` |
   | `VITE_POSTHOG_KEY` | PostHog project key |
   | `VITE_POSTHOG_HOST` | `/ingest` |
   | `VITE_POSTHOG_UI_HOST` | `https://us.posthog.com` |
   | `VITE_SENTRY_DSN` | `artha-web` DSN |
   | `VITE_VAPID_PUBLIC_KEY` | Public VAPID key for Web Push (`npx --yes web-push generate-vapid-keys --json`; see `docs/X-01-ROLLOUT.md` section 1). Optional until push is rolled out; redeploy after adding it |
   | `SENTRY_AUTH_TOKEN` | Sentry org token (build time only) |
   | `SENTRY_ORG` | Sentry org slug |
   | `SENTRY_PROJECT` | `artha-web` |

   `VITE_*` values are baked in at build time. After changing any, **redeploy**.
6. **Deploy**, then add your domain under **Settings -> Domains** (apex + `www`, pick one as primary).
7. Go back to the **api** project and make sure `CORS_ALLOWED_ORIGINS` and `DJANGO_ALLOWED_HOSTS` match the final domains, then redeploy the api.

---

## 8. Verify end to end

1. Open the site: landing page loads, planner sliders work.
2. **WhatsApp preview**: paste `https://yourdomain.com` and a deep link such as `/features/study-planner` into WhatsApp. If it shows a stale or empty card, run the URL through the **Facebook Sharing Debugger** (developers.facebook.com/tools/debug) and click **Scrape Again**. WhatsApp caches previews.
3. `https://yourdomain.com/sitemap.xml` and `/robots.txt` return content with your real domain.
4. **Sign in**: click Start free -> Google, email code or password -> you land on `/app` and see your email. Open **/app/account** and check the theme picker (Reading, Light, Dark, System).
5. **API call**: in the browser console on `/app` (after login) or via the Network tab, `GET /api/v1/me/` returns your profile (it is created on first call).
6. **Sentry**: temporarily throw an error in a route and confirm it appears. **PostHog**: Activity shows `$pageview`.
7. Submit the sitemap in **Google Search Console** (add property, verify DNS, submit `/sitemap.xml`).

### 8.1 How to verify a link preview (do this after every web deploy that touches SEO)

1. Confirm the env: Vercel -> `arthacommerce-web` -> Settings -> Environment Variables. `VITE_SITE_URL` is exactly `https://arthacommerce.meetpawan.com` (origin only). After any change, **Redeploy** (values are baked in at build time).
2. View the server HTML (not the DOM inspector): browser `view-source:https://<domain>/`. Inside the first 300 KB of `<head>`, find `og:title`, `og:description`, `og:url`, `og:image` (absolute `https://`, same host), `og:image:width` 1200, `og:image:height` 630, `twitter:card`, `canonical`. Repeat for `/features`, `/courses`, `/courses/ca` and one chapter: each must show its own title and description.
3. Open the `og:image` URL directly: it must load in a normal tab without login or redirect, as a 1200x630 PNG under 300 KB.
4. Open `/robots.txt` (no `Disallow: /`, Sitemap line has the right host) and `/sitemap.xml` (every `<loc>` opens).
5. Facebook Sharing Debugger (developers.facebook.com/tools/debug): paste the URL, press **Scrape Again**. It uses the same crawler as WhatsApp (`facebookexternalhit`) and shows the exact tags and any warning.
6. WhatsApp: send the link to yourself or a test group. **WhatsApp caches previews** (the result of a first, broken scrape can stick for days). To bust it, share the URL with a throwaway query string, e.g. `https://<domain>/?v=2` (a new URL is a new cache entry), and use Scrape Again in the Sharing Debugger for the clean URL. If a phone still shows the old card, clear WhatsApp's cache or test from another phone.
7. Also check with LinkedIn Post Inspector, opengraph.xyz and, for JSON-LD, Google's Rich Results Test.

---

## 9. Daily local development

```bash
# terminal 1
pnpm dev:web                     # http://localhost:3000

# terminal 2
cd apps/api && source .venv/bin/activate
set -a && source .env && set +a
export DJANGO_DEBUG=true
python manage.py runserver 8000  # uses SQLite unless DATABASE_URL is set
```

`apps/web/.env.local` minimum: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_URL=http://localhost:8000`.
For the API to accept your Supabase tokens locally, set `SUPABASE_URL` (and `SUPABASE_JWT_SECRET` if legacy) in `apps/api/.env`, then `set -a; source .env; set +a`.

Checks before every PR:

```bash
pnpm check
pnpm lint:api && pnpm test:api
```

---

## 10. Environment variable master list

| Variable | Web | API | Secret? |
| --- | :-: | :-: | :-: |
| `VITE_SITE_URL`, `VITE_SITE_NAME` | yes | | no |
| `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` | yes | | no (public by design) |
| `VITE_API_URL` | yes | | no |
| `VITE_POSTHOG_KEY`, `VITE_POSTHOG_HOST`, `VITE_POSTHOG_UI_HOST` | yes | | no |
| `VITE_SENTRY_DSN` | yes | | no |
| `VITE_VAPID_PUBLIC_KEY`, `VITE_SW_DEV` | yes | | no (public by design) |
| `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT` | yes (build) | | **yes** |
| `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` | | yes | **yes** (secret key) |
| `DATABASE_URL`, `DIRECT_DATABASE_URL` | | yes | **yes** |
| `SUPABASE_URL`, `SUPABASE_JWT_SECRET` | | yes | JWT secret **yes** |
| `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_AVATAR_BUCKET` | | yes | service role key **yes** (never in the web project) |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | | yes | **yes** (key) |
| `NOTES_TICK_SECRET` (F-03 notes cron tick; set `CRON_SECRET` to the same value for Vercel Cron) | | yes | **yes** |
| `MEDIA_SCANNER` (F-03 R2: `null` clean at once, development only, or `clamd`; **must be `clamd` in production**), `CLAMD_HOST`, `CLAMD_PORT` (3310), `CLAMD_SOCKET` (wins over host and port; clamd needs `StreamMaxLength 64M`). Used by the worker's `media.scan` job | | yes (worker) | no |
| `SENTRY_DSN` | | yes | no |
| `WORKER_TYPE_LIMITS`, `WORKER_SHUTDOWN_GRACE_SECONDS`, `WORKER_HEARTBEAT_SECONDS`, `WORKER_FONTS_DIR`, `WORKER_LIVENESS_FILE` (F-03 PDF worker container only, see `docs/F-03-WORKER.md`) | | worker | no |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_USE_TLS`, `EMAIL_BACKEND`, `EMAIL_TIMEOUT`, `NOTIFICATIONS_EMAIL_FROM` (weekly email) | | yes | no |
| `EMAIL_HOST_PASSWORD` (weekly email) | | yes | **yes** |

Rule: nothing secret ever gets a `VITE_` prefix. Google and SMTP credentials stay in the Supabase dashboard.

---

## 11. Troubleshooting

- **Login redirects to localhost in production**: Supabase **Site URL** and **Redirect URLs** are wrong.
- **Emails do not arrive, or only some do**: you are still on Supabase's built-in sender (section 2.3.1), or SPF, DKIM or DMARC are missing. Check the provider's logs.
- **"This link did not work" on /auth/confirm**: the link was already used or is older than 60 minutes. Request a new one. Make sure the Site URL matches the domain the student is on.
- **Email shows `{{ .Something }}` text**: the template was pasted into the wrong dashboard slot, or contains a variable Supabase does not know. Regenerate with `pnpm emails:build` and paste the whole file.
- **Theme looks wrong on first load**: the head script that sets the theme must stay in `apps/web/src/routes/__root.tsx`. Reading is the default; System means light 6 am to 6 pm, dark 6 pm to 6 am on the device clock.
- **API returns 401 for a valid login**: `SUPABASE_URL` missing on the api, or a legacy project needs `SUPABASE_JWT_SECRET`.
- **CORS error in the browser**: add the exact web origin (scheme + host, no trailing slash) to `CORS_ALLOWED_ORIGINS` and redeploy the api.
- **`prepared statement ... already exists`**: you pointed `DATABASE_URL` at the session/direct port. Use the transaction pooler (6543) for runtime.
- **Migrate hangs**: run it with `DIRECT_DATABASE_URL` (5432), never the 6543 pooler.
- **WhatsApp shows only the bare host, or no image**: view the page source and check `og:image`. It must be `https://<your domain>/og/default.png` and open in a browser. Causes seen: `VITE_SITE_URL` contained a path (`https://domain/login`, so every URL became `.../login/og/default.png`, a 404) or was unset; the image is over about 300 KB; WhatsApp cached the earlier bad result (see 8.1).
- **Sentry shows minified stack traces**: the three `SENTRY_*` build vars are missing in the web project.
