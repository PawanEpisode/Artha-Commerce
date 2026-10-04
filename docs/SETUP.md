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
  - Do **not** use the `service_role` / secret key anywhere yet. It is not needed.
- **Connect -> Connection string**:
  - **Transaction pooler** (port **6543**) -> `DATABASE_URL` (api runtime)
  - **Session pooler** or **Direct** (port **5432**) -> `DIRECT_DATABASE_URL` (api migrations)
  - Replace `[YOUR-PASSWORD]` in both.
- **Project Settings -> JWT Keys**: new projects use asymmetric signing keys and the API reads them automatically from `SUPABASE_URL`. Only if your project still shows a **legacy JWT secret** in use, copy it to `SUPABASE_JWT_SECRET` (api).

### 2.3 Authentication
1. **Authentication -> Sign In / Providers**: make sure **Email** is enabled (magic link / OTP).
2. **Google provider**:
   - console.cloud.google.com -> create/select a project -> **APIs & Services -> OAuth consent screen** (External, add your email and app name).
   - **Credentials -> Create credentials -> OAuth client ID -> Web application**.
   - Authorised redirect URI: `https://<your-project-ref>.supabase.co/auth/v1/callback` (shown in the Supabase Google provider panel).
   - Paste the Client ID and Secret into Supabase **Google** provider and enable it.
3. **Authentication -> URL Configuration**:
   - **Site URL**: your production web URL (use `http://localhost:3000` until you have one)
   - **Redirect URLs** (add all):
     - `http://localhost:3000/auth/callback`
     - `https://<your-prod-domain>/auth/callback`
     - `https://*-<your-vercel-team-slug>.vercel.app/auth/callback` (preview deployments)
4. **Authentication -> SMTP (before launch)**: the built-in email sender is heavily rate limited. Configure a custom SMTP provider (Resend, Postmark, SES) so sign-in emails are reliable.

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
   | `DATABASE_URL` | Supabase **transaction pooler** string (port 6543) |
   | `DIRECT_DATABASE_URL` | Supabase direct/session string (port 5432) |
   | `SUPABASE_URL` | `https://<ref>.supabase.co` |
   | `SUPABASE_JWT_SECRET` | only if your project uses the legacy HS256 secret |
   | `GEMINI_API_KEY` | from AI Studio |
   | `GEMINI_MODEL` | optional |
   | `SENTRY_DSN` | `artha-api` DSN |

5. **Deploy**. Then open `https://<api-url>/api/v1/health/ready/`. Expect `{"status":"ok","database":"up"}`.
6. **Settings -> Domains**: add `api.yourdomain.com` and follow the DNS instructions.

> Vercel Python reads `apps/api/requirements.txt` and `.python-version` (3.12). It detects Django from `manage.py` and serves `config/wsgi.py`. Do not rewrite every path to `/api/index`: that replaces the request path, so `/api/v1/health/ready/` never matches.

---

## 7. Vercel: Web project

1. **Add New -> Project** -> same GitHub repo.
2. **Project name**: `arthacommerce-web`.
3. **Root Directory**: `apps/web`. Keep **Include source files outside of the Root Directory** enabled.
4. Framework is taken from `apps/web/vercel.json` (`tanstack-start`). Install command default (`pnpm install`) works with the root workspace.
5. **Environment Variables** (Production and Preview):

   | Name | Value |
   | --- | --- |
   | `VITE_SITE_URL` | `https://yourdomain.com` (**must be the real public URL**, drives canonical and WhatsApp previews) |
   | `VITE_SITE_NAME` | `ArthaCommerce` |
   | `VITE_SUPABASE_URL` | Supabase project URL |
   | `VITE_SUPABASE_ANON_KEY` | Supabase publishable/anon key |
   | `VITE_API_URL` | `https://api.yourdomain.com` |
   | `VITE_POSTHOG_KEY` | PostHog project key |
   | `VITE_POSTHOG_HOST` | `/ingest` |
   | `VITE_POSTHOG_UI_HOST` | `https://us.posthog.com` |
   | `VITE_SENTRY_DSN` | `artha-web` DSN |
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
4. **Sign in**: click Start free -> Google or email link -> you land on `/app` and see your email.
5. **API call**: in the browser console on `/app` (after login) or via the Network tab, `GET /api/v1/me/` returns your profile (it is created on first call).
6. **Sentry**: temporarily throw an error in a route and confirm it appears. **PostHog**: Activity shows `$pageview`.
7. Submit the sitemap in **Google Search Console** (add property, verify DNS, submit `/sitemap.xml`).

---

## 9. Daily local development

```bash
# terminal 1
pnpm dev:web                     # http://localhost:3000

# terminal 2
cd apps/api && source .venv/bin/activate
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
| `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT` | yes (build) | | **yes** |
| `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` | | yes | **yes** (secret key) |
| `DATABASE_URL`, `DIRECT_DATABASE_URL` | | yes | **yes** |
| `SUPABASE_URL`, `SUPABASE_JWT_SECRET` | | yes | JWT secret **yes** |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | | yes | **yes** (key) |
| `SENTRY_DSN` | | yes | no |

Rule: nothing secret ever gets a `VITE_` prefix.

---

## 11. Troubleshooting

- **Login redirects to localhost in production**: Supabase **Site URL** and **Redirect URLs** are wrong.
- **API returns 401 for a valid login**: `SUPABASE_URL` missing on the api, or a legacy project needs `SUPABASE_JWT_SECRET`.
- **CORS error in the browser**: add the exact web origin (scheme + host, no trailing slash) to `CORS_ALLOWED_ORIGINS` and redeploy the api.
- **`prepared statement ... already exists`**: you pointed `DATABASE_URL` at the session/direct port. Use the transaction pooler (6543) for runtime.
- **Migrate hangs**: run it with `DIRECT_DATABASE_URL` (5432), never the 6543 pooler.
- **WhatsApp shows no image**: `VITE_SITE_URL` is wrong, or the image is over about 300 KB, or the cache needs a Sharing Debugger refresh.
- **Sentry shows minified stack traces**: the three `SENTRY_*` build vars are missing in the web project.
