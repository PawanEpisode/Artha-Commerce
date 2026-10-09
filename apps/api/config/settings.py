"""
Django settings, configured entirely through environment variables (12-factor).
The API is stateless: auth is a Supabase JWT per request, no sessions, no server-side files.
"""

import os
import sys
from pathlib import Path

import dj_database_url
import sentry_sdk

from core.sentry import before_send

BASE_DIR = Path(__file__).resolve().parent.parent


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def env_list(key: str, default: str = "") -> list[str]:
    return [v.strip() for v in env(key, default).split(",") if v.strip()]


DEBUG = env("DJANGO_DEBUG", "false").lower() == "true"
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-key" if DEBUG else "")
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false")


def allowed_hosts() -> list[str]:
    """Configured hosts, the Vercel production domain (when provided) and any *.vercel.app preview."""
    hosts = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
    production_url = env("VERCEL_PROJECT_PRODUCTION_URL").strip()
    if production_url:
        hosts.append(production_url)
    return [*hosts, ".vercel.app"]


ALLOWED_HOSTS = allowed_hosts()


def csrf_trusted_origins() -> list[str]:
    """Origins allowed to POST to the admin. Includes the Vercel production domain."""
    origins = env_list("CSRF_TRUSTED_ORIGINS")
    production = env("VERCEL_PROJECT_PRODUCTION_URL").strip().split("/")[0]
    if production:
        origin = f"https://{production}"
        if origin not in origins:
            origins.append(origin)
    return origins


INSTALLED_APPS = [
    "django.contrib.admin",  # staff-only content admin at /<DJANGO_ADMIN_PATH> (not used by students)
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "core",
    "modules.profiles",
    "modules.syllabus",
    "modules.coverage",
    "modules.tracking",
    "modules.focus",
    "modules.notifications",
    "modules.media",
    "modules.notes",
    "modules.recall",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # serves the admin's CSS/JS (no collectstatic step on Vercel)
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

# Admin location. Change it per environment to keep scanners away; the default is fine locally.
ADMIN_PATH = env("DJANGO_ADMIN_PATH", "admin").strip("/") + "/"
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
WHITENOISE_USE_FINDERS = True  # serve straight from the installed apps: nothing to build or deploy
CSRF_TRUSTED_ORIGINS = csrf_trusted_origins()

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Database (Supabase Postgres) -------------------------------------------------------------
# Runtime uses the transaction pooler; `migrate` needs a direct/session connection (DDL, advisory locks).
_is_migrating = len(sys.argv) > 1 and sys.argv[1] in {"migrate", "makemigrations", "sqlmigrate"}
_db_url = (
    (env("DIRECT_DATABASE_URL") if _is_migrating else "")
    or env("DATABASE_URL")
    or f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
)
DATABASES = {"default": dj_database_url.parse(_db_url, conn_max_age=0)}
if DATABASES["default"]["ENGINE"].endswith("postgresql"):
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True  # required by pgbouncer transaction mode
    DATABASES["default"].setdefault("OPTIONS", {})["prepare_threshold"] = None

# Per-instance cache (flag answers use their own in-process cache; this is for small derived values and throttles).
# Serverless instances do not share it, so nothing correctness-critical may live here: quotas are database facts.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "artha-default"}}

# --- API ---------------------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["core.authentication.SupabaseJWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "core.exceptions.api_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "core.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "300/min",
        # Scoped throttles (ScopedRateThrottle), see modules.syllabus and modules.coverage views.
        "syllabus_report": "20/hour",
        "coverage_write": "120/min",
        "tracking_write": "60/min",
        "tracking_reports": "120/min",
        "tracking_export": "6/hour",
        "focus_write": "120/min",
        # F-16 profile, onboarding and account data
        "profile_write": "30/min",
        "avatar_write": "10/hour",
        "lastvisit_write": "20/min",
        "onboarding_write": "60/min",
        "account_export": "3/hour",
        "account_delete": "3/day",
        # X-01 notifications
        "notifications_read": "120/min",
        "notifications_write": "60/min",
        "notifications_test": "5/min",
        "notifications_unsubscribe": "20/min",
        "notifications_action": "30/min",
        # F-03 notes (PRD 9). Cost-bearing limits are database quotas, not throttles: throttle state is per instance.
        "notes_read": "300/min",
        "notes_write": "600/min",
        "notes_search": "60/min",
        "notes_account": "6/hour",
        "notes_upload": "30/hour",  # R2: reserving PDF uploads
        "notes_export": "6/hour",  # R2: building flattened PDFs and archives
        "notes_unlock": "20/hour",  # R3: trying a password on a locked PDF (also capped per document in the database)
        "notes_ai": "20/hour",  # R3: asking for an AI summary or page reading (the money limit is the monthly quota)
        # F-15 recall: reviews are never limited by plan, so these are only politeness (PRD 9)
        "recall_review": "600/min",  # W5: review events and batches
        "recall_write": "120/min",  # card, deck and settings writes
        "recall_export": "6/hour",  # W11: streamed CSV and JSON export
        "media_upload": "120/hour",
        "media_read": "300/min",
    },
    "UNAUTHENTICATED_USER": None,
}

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
CORS_ALLOW_CREDENTIALS = False  # bearer tokens, not cookies
# The queue and the scheduler call `notifications/internal/` server to server: never a browser, so never CORS.
CORS_URLS_REGEX = r"^(?!/api/v1/(notifications|notes|recall)/internal/).*$"

# --- Supabase / Gemini ------------------------------------------------------------------------
SUPABASE_URL = env("SUPABASE_URL").rstrip("/")
SUPABASE_JWT_SECRET = env("SUPABASE_JWT_SECRET")  # legacy HS256 projects; asymmetric keys are read from JWKS
# Feature flags (PostHog). Leave the key empty to treat every flag as on (local development, tests).
# Service-role key: Storage writes (avatars) and the Auth Admin API (account deletion). API only, never `VITE_*`, never logged.
SUPABASE_SERVICE_ROLE_KEY = env("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_AVATAR_BUCKET = env("SUPABASE_AVATAR_BUCKET", "avatars")
# POSTHOG_API_KEY is the project API key (starts with phc_), the same one the web uses as VITE_POSTHOG_KEY.
POSTHOG_API_KEY = env("POSTHOG_API_KEY")
POSTHOG_HOST = env("POSTHOG_HOST", "https://us.i.posthog.com")  # the real host, not the web's /ingest proxy
POSTHOG_FLAG_TIMEOUT_SECONDS = float(env("POSTHOG_FLAG_TIMEOUT_SECONDS", "1.5"))
FEATURE_FLAG_CACHE_SECONDS = int(env("FEATURE_FLAG_CACHE_SECONDS", "60"))
# --- Notifications (X-01.1) -------------------------------------------------------------------
# Master kill switch, read at start-up and OFF by default: nothing is scheduled or sent until it is set to "true".
# The PostHog flag `push_notifications` (strict for sending) is the fast switch; this is the hard stop.
NOTIFICATIONS_ENABLED = env("NOTIFICATIONS_ENABLED", "false").lower() == "true"
NOTIFICATIONS_DISABLED_EVENTS = frozenset(env_list("NOTIFICATIONS_DISABLED_EVENTS"))  # event keys switched off
NOTIFICATIONS_QUEUE = env("NOTIFICATIONS_QUEUE", "null")  # "null" (local, tests) or "qstash"
NOTIFICATIONS_PUBLIC_BASE_URL = env("NOTIFICATIONS_PUBLIC_BASE_URL").rstrip("/")  # origin the queue calls back
# Declarative push (FR-N35): extra fields so Safari on iOS 18.4+ can show an alert without waking the worker. Off until
# the Safari spike has passed on a real device. It needs the web origin, because the link in the message is absolute.
NOTIFICATIONS_DECLARATIVE_PUSH = env("NOTIFICATIONS_DECLARATIVE_PUSH", "false").lower() == "true"
NOTIFICATIONS_WEB_BASE_URL = env("NOTIFICATIONS_WEB_BASE_URL").rstrip("/")  # e.g. https://app.example.com
if NOTIFICATIONS_DECLARATIVE_PUSH and not NOTIFICATIONS_WEB_BASE_URL.startswith("https://"):
    raise RuntimeError("NOTIFICATIONS_DECLARATIVE_PUSH needs NOTIFICATIONS_WEB_BASE_URL set to an https URL")
VAPID_PRIVATE_KEY = env("VAPID_PRIVATE_KEY")
VAPID_SUBJECT = env("VAPID_SUBJECT")  # mailto: role address, shown to push services
QSTASH_TOKEN = env("QSTASH_TOKEN")
QSTASH_URL = env("QSTASH_URL")
QSTASH_CURRENT_SIGNING_KEY = env("QSTASH_CURRENT_SIGNING_KEY")
QSTASH_NEXT_SIGNING_KEY = env("QSTASH_NEXT_SIGNING_KEY")
CRON_SECRET = env("CRON_SECRET")  # bearer secret for the sweep endpoint
# F-03 notes: shared secret for the cron tick `/api/v1/notes/internal/tick/` (header X-Notes-Tick-Secret or Authorization: Bearer).
# Empty means the tick refuses every caller. For Vercel Cron, which can only send `Authorization: Bearer $CRON_SECRET`, set it
# to the same value as CRON_SECRET.
NOTES_TICK_SECRET = env("NOTES_TICK_SECRET")
# F-15 recall (flag `recall_system`, fails closed). RECALL_TICK_SECRET guards the cron tick that arrives in W5 (same rules as
# NOTES_TICK_SECRET: empty refuses every caller). RECALL_PACK_MAX caps the offline pack a client may ask for, whatever the
# plan allows (W6). RECALL_DEFAULT_WEIGHTS_VERSION names the seeded default parameter set new cards start on.
RECALL_TICK_SECRET = env("RECALL_TICK_SECRET")
RECALL_PACK_MAX = int(env("RECALL_PACK_MAX", "500"))
RECALL_DEFAULT_WEIGHTS_VERSION = env("RECALL_DEFAULT_WEIGHTS_VERSION", "fsrs-6.0")
# Upload scanning (F-03 R2, media). `null` marks files clean without scanning (development and tests only); `clamd` streams them
# to a ClamAV daemon over a unix socket (CLAMD_SOCKET, wins when set) or TCP (CLAMD_HOST, CLAMD_PORT). clamd needs
# `StreamMaxLength 64M`. The scan itself runs in the worker (`media.scan` job).
MEDIA_SCANNER = env("MEDIA_SCANNER", "null").lower()
CLAMD_HOST = env("CLAMD_HOST")
CLAMD_PORT = int(env("CLAMD_PORT", "3310"))
CLAMD_SOCKET = env("CLAMD_SOCKET")
# Weekly email (W3.5). The backend is SMTP in production and the console in development; sending needs a From address.
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_TIMEOUT = int(env("EMAIL_TIMEOUT", "10"))
NOTIFICATIONS_EMAIL_FROM = env(
    "NOTIFICATIONS_EMAIL_FROM"
)  # e.g. "ArthaCommerce <hello@mail.example.com>"; empty disables sending
FIELD_ENCRYPTION_KEYS = env_list("FIELD_ENCRYPTION_KEYS")  # Fernet keys, newest first (core.fields)
FIELD_HASH_PEPPER = env("FIELD_HASH_PEPPER")
if NOTIFICATIONS_ENABLED and not DEBUG and not (FIELD_ENCRYPTION_KEYS and FIELD_HASH_PEPPER):
    raise RuntimeError("NOTIFICATIONS_ENABLED needs FIELD_ENCRYPTION_KEYS and FIELD_HASH_PEPPER to be set")

GEMINI_API_KEY = env("GEMINI_API_KEY")
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-flash-latest")
GEMINI_TIMEOUT_SECONDS = int(env("GEMINI_TIMEOUT_SECONDS", "90") or 90)
# F-03 R3 (flag `notes_ai`). Every one of these fails closed: AI costs money and sends a student's text to Google.
# `paid` only when the key's Google Cloud project has an active billing account (Gemini API "Paid Services": Google does not
# use the content to improve its products). A consumer Gemini or Google AI Pro subscription does NOT count.
GEMINI_DATA_TIER = env("GEMINI_DATA_TIER", "unconfirmed").lower()
# The owner sets this to the consent version they approved (see modules/notes/domain/ai_consent.py); empty keeps AI off.
NOTES_AI_CONSENT_APPROVED = env("NOTES_AI_CONSENT_APPROVED")
NOTES_AI_SUMMARY_ENABLED = env("NOTES_AI_SUMMARY_ENABLED", "true").lower() == "true"  # kill switch
NOTES_AI_OCR_ENABLED = env("NOTES_AI_OCR_ENABLED", "true").lower() == "true"  # kill switch
NOTES_AI_DAILY_BUDGET_PAISE = int(env("NOTES_AI_DAILY_BUDGET_PAISE", "0") or 0)  # all students, India day; 0 = AI off
# Unlock for search: Fernet keys (comma separated, newest first; `Fernet.generate_key()`) that seal a password for the hour it
# is needed. Empty keeps the feature off (503 `unlock_unavailable`).
NOTES_UNLOCK_FERNET_KEYS = env("NOTES_UNLOCK_FERNET_KEYS")
# Resumable upload of big PDFs: Supabase Storage's S3 endpoint (Project settings, Storage, S3 connection) and an S3 access key.
# All three empty keeps every upload a single signed PUT. [VERIFY] with one real upload before switching `notes_ai` on.
NOTES_S3_ENDPOINT = env("NOTES_S3_ENDPOINT")  # https://<project-ref>.storage.supabase.co/storage/v1/s3
NOTES_S3_REGION = env("NOTES_S3_REGION")
NOTES_S3_ACCESS_KEY_ID = env("NOTES_S3_ACCESS_KEY_ID")
NOTES_S3_SECRET_ACCESS_KEY = env("NOTES_S3_SECRET_ACCESS_KEY")
# Price table in paise per million tokens (ERD 6.1 list price, assumptions to re-check): used to compute `cost_paise`.
GEMINI_PRICE_IN_PAISE_PER_M = int(env("GEMINI_PRICE_IN_PAISE_PER_M", "13200") or 13200)
GEMINI_PRICE_OUT_PAISE_PER_M = int(env("GEMINI_PRICE_OUT_PAISE_PER_M", "79200") or 79200)

# --- Security ---------------------------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = False  # Vercel terminates TLS and redirects
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True  # admin login cookie
    CSRF_COOKIE_SECURE = True

# --- Observability ----------------------------------------------------------------------------
if env("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=env("SENTRY_DSN"),
        traces_sample_rate=0.1,
        send_default_pii=False,
        before_send=before_send,
    )

LANGUAGE_CODE = "en-in"
TIME_ZONE = "UTC"
USE_TZ = True
USE_I18N = False
