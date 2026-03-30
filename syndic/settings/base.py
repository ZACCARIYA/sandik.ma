"""Base Django settings shared by all environments."""

import json
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    """Return boolean value from environment variable."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

def env_json(name, default=None):
    """Parse a JSON string from an environment variable."""
    raw = os.getenv(name)
    if raw in (None, ""):
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON for {name}: {exc}") from exc


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key")
DEBUG = env_bool("DJANGO_DEBUG", False)

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver,.up.railway.app").split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "https://*.up.railway.app,https://sandikma.up.railway.app").split(",")
    if origin.strip()
]


INSTALLED_APPS = [
    "django_mongodb_backend",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "crispy_forms",
    "crispy_bootstrap5",
    "accounts",
    "finance",
    "residents",
    "documents",
    "notifications",
    "tickets",
    "properties",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "syndic.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "syndic.wsgi.application"
ASGI_APPLICATION = "syndic.asgi.application"


DB_ENGINE = os.getenv("DB_ENGINE", "django.db.backends.sqlite3")
DB_NAME_ENV = os.getenv("DB_NAME")

if DB_NAME_ENV:
    if DB_ENGINE == "django.db.backends.sqlite3" and not os.path.isabs(DB_NAME_ENV):
        database_name = BASE_DIR / DB_NAME_ENV
    else:
        database_name = DB_NAME_ENV
else:
    database_name = BASE_DIR / "db.sqlite3" if DB_ENGINE == "django.db.backends.sqlite3" else "syndic_db"

database_options = env_json("DB_OPTIONS")

default_database = {
    "ENGINE": DB_ENGINE,
    "NAME": database_name,
    "USER": os.getenv("DB_USER", ""),
    "PASSWORD": os.getenv("DB_PASSWORD", ""),
    "HOST": os.getenv("DB_HOST", ""),
    "PORT": os.getenv("DB_PORT", ""),
}

if database_options:
    default_database["OPTIONS"] = database_options

DATABASES = {"default": default_database}


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Casablanca"
USE_I18N = True
USE_TZ = True


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Simplified static file serving.
# https://warehouse.python.org/project/whitenoise/
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.StaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = (
    "django_mongodb_backend.fields.ObjectIdAutoField"
    if DB_ENGINE == "django_mongodb_backend"
    else "django.db.models.BigAutoField"
)

# Silence MongoDB AutoField error for built-in apps
if DB_ENGINE == "django_mongodb_backend":
    SILENCED_SYSTEM_CHECKS = ["mongodb.E001"]

AUTH_USER_MODEL = "accounts.User"
CRISPY_TEMPLATE_PACK = "bootstrap5"


EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@syndic.local")

SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8000")


# Local in-memory caching can be replaced with Redis in production.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "syndic-default-cache",
    }
}

LOGIN_URL = "finance:login"
LOGIN_REDIRECT_URL = "finance:home"
LOGOUT_REDIRECT_URL = "finance:home"
