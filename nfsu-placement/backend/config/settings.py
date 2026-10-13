"""Settings for the NFSU Placement Management System.

Every secret comes from the environment (.env in development). Security-relevant
defaults are strict; DEBUG only relaxes the HTTPS-only cookie flags.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required environment variable {name}. Run the setup script or copy .env.example to .env.")
    return value


def env_bool(name, default=False):
    return str(os.environ.get(name, default)).lower() in {"1", "true", "yes", "on"}


SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env("CSRF_TRUSTED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

# Column-level encryption (Fernet) and blind index (HMAC) keys.
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", required=True)
BLIND_INDEX_KEY = env("BLIND_INDEX_KEY", required=True)

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
    "apps.accounts",
    "apps.audit",
    "apps.approvals",
    "apps.students",
    "apps.recruiters",
    "apps.placements",
    "apps.policy",
    "apps.bulletin",
    "apps.analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

# Database: SQLite for zero-setup local runs, PostgreSQL for the real deployment.
if env("DB_ENGINE", "sqlite") == "postgres":
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "nfsu_placement"),
        "USER": env("POSTGRES_USER", "nfsu_app"),
        "PASSWORD": env("POSTGRES_PASSWORD", required=True),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
    }}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_USER_MODEL = "accounts.User"
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Sessions: 15-minute idle timeout, cookie unreadable by JavaScript.
SESSION_COOKIE_AGE = 15 * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = False  # React must read it to send X-CSRFToken
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Activation links for recruiters (single use, expires after 24 h).
PASSWORD_RESET_TIMEOUT = 24 * 60 * 60

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser", "rest_framework.parsers.MultiPartParser"],
    "EXCEPTION_HANDLER": "core.exceptions.safe_exception_handler",
}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
if env("REDIS_URL"):
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": env("REDIS_URL")}}

EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "placement-cell@nfsu.local")
PLACEMENT_CELL_EMAIL = env("PLACEMENT_CELL_EMAIL", "placement-cell@nfsu.local")
FRONTEND_URL = env("FRONTEND_URL", "http://localhost:5173")

# Private uploads: never exposed through a public URL.
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"
RESUME_MAX_BYTES = 2 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 3 * 1024 * 1024

# Project security knobs.
REQUIRE_STAFF_MFA = env_bool("REQUIRE_STAFF_MFA", False)
LOGIN_MAX_FAILURES = 5
LOGIN_LOCK_MINUTES = 15
PUBLIC_STATS_MIN_CELL = int(env("PUBLIC_STATS_MIN_CELL", "5"))
CHANGE_REQUEST_TTL_HOURS = 48
EXPORT_ROW_CAP = 2000

LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"nfsu": {"handlers": ["console"], "level": "INFO"}},
}
