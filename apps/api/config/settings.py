"""
Django settings, configured entirely through environment variables (12-factor).
The API is stateless: auth is a Supabase JWT per request, no sessions, no server-side files.
"""

import os
import sys
from pathlib import Path

import dj_database_url
import sentry_sdk

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
    """Hosts Django will serve.

    `.vercel.app` covers generated deployment URLs. Vercel sets
    `VERCEL_PROJECT_PRODUCTION_URL` to the production custom domain.
    """
    hosts = [*env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1"), ".vercel.app"]
    production = env("VERCEL_PROJECT_PRODUCTION_URL").strip().split("/")[0]
    if production and production not in hosts:
        hosts.append(production)
    return hosts


ALLOWED_HOSTS = allowed_hosts()

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "corsheaders",
    "rest_framework",
    "core",
    "modules.profiles",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

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
    "DEFAULT_THROTTLE_RATES": {"anon": "60/min", "user": "300/min"},
    "UNAUTHENTICATED_USER": None,
}

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
CORS_ALLOW_CREDENTIALS = False  # bearer tokens, not cookies

# --- Supabase / Gemini ------------------------------------------------------------------------
SUPABASE_URL = env("SUPABASE_URL").rstrip("/")
SUPABASE_JWT_SECRET = env("SUPABASE_JWT_SECRET")  # legacy HS256 projects; asymmetric keys are read from JWKS
GEMINI_API_KEY = env("GEMINI_API_KEY")
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-flash-latest")

# --- Security ---------------------------------------------------------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = False  # Vercel terminates TLS and redirects
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

# --- Observability ----------------------------------------------------------------------------
if env("SENTRY_DSN"):
    sentry_sdk.init(dsn=env("SENTRY_DSN"), traces_sample_rate=0.1, send_default_pii=False)

LANGUAGE_CODE = "en-in"
TIME_ZONE = "UTC"
USE_TZ = True
USE_I18N = False
