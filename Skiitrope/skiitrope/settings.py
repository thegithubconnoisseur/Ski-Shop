"""Django settings for the Skiitrope shop."""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = env("DJANGO_SECRET_KEY", "django-insecure-change-me-in-production")
DEBUG = env_bool("DJANGO_DEBUG", not env("RENDER"))
ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# Render injects RENDER_EXTERNAL_HOSTNAME (e.g. skiitrope.onrender.com) on
# every deploy, so the live host is trusted without manual config.
RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    # Third party
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "django_countries",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    # Local
    "accounts",
    "store",
    "cart",
    "orders",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "skiitrope.urls"

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
                "cart.context_processors.cart",
            ],
        },
    },
]

WSGI_APPLICATION = "skiitrope.wsgi.application"
ASGI_APPLICATION = "skiitrope.asgi.application"

# Database: Supabase Postgres when DATABASE_URL is set (e.g. the connection
# string from Supabase → Project Settings → Database), SQLite otherwise so the
# project runs out of the box during local development.
DATABASE_URL = env("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=int(env("DB_CONN_MAX_AGE", "0")),
            conn_health_checks=True,
            ssl_require=True,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Logging ---------------------------------------------------------------

# Django's default logging only prints request tracebacks when DEBUG=True
# (the console handler is filtered by require_debug_true), so production
# 500s leave no traceback in the logs. Always send them to stderr, which
# Render's Logs tab displays.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
        "server": {
            "()": "django.utils.log.ServerFormatter",
            "format": "[{server_time}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "server_console": {"class": "logging.StreamHandler", "formatter": "server"},
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["server_console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# --- Auth / allauth -------------------------------------------------------

LOGIN_REDIRECT_URL = "store:home"
ACCOUNT_LOGOUT_REDIRECT_URL = "store:home"
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_UNIQUE_EMAIL = True
SOCIALACCOUNT_LOGIN_ON_GET = True

GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", "")

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": GOOGLE_CLIENT_ID,
            "secret": GOOGLE_CLIENT_SECRET,
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online", "prompt": "select_account"},
        "OAUTH_PKCE_ENABLED": True,
    }
}

SITE_ID = 1

# --- API (mobile app) -----------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
}

# CORS: only active when CORS_ALLOWED_ORIGINS is set, so the deployed site
# stays locked down while local dev (e.g. the Expo web app on :8081) can hit
# the API from the browser.
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in env("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]

# --- Email: Mailgun via django-anymail (console backend without a key) ----

MAILGUN_API_KEY = env("MAILGUN_API_KEY", "")
MAILGUN_SENDER_DOMAIN = env("MAILGUN_SENDER_DOMAIN", "")
MAILGUN_API_URL = env("MAILGUN_API_URL", "https://api.mailgun.net/v3")

DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Skiitrope <orders@skiitrope.com>")
SERVER_EMAIL = env("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
ORDER_NOTIFICATION_EMAIL = env("ORDER_NOTIFICATION_EMAIL", "")

if MAILGUN_API_KEY and MAILGUN_SENDER_DOMAIN:
    MAILERS = {
        "default": {
            "BACKEND": "anymail.backends.mailgun.EmailBackend",
            "OPTIONS": {"fail_silently": False},
        }
    }
    ANYMAIL = {
        "MAILGUN_API_KEY": MAILGUN_API_KEY,
        "MAILGUN_SENDER_DOMAIN": MAILGUN_SENDER_DOMAIN,
        "MAILGUN_API_URL": MAILGUN_API_URL,
    }
else:
    MAILERS = {
        "default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}
    }

# --- Payments: Stripe (USD, international cards) --------------------------

STRIPE_PUBLIC_KEY = env("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", "")

# --- Shop -----------------------------------------------------------------

SHOP_CURRENCY = "USD"
SHOP_CURRENCY_SYMBOL = "$"
FREE_SHIPPING_THRESHOLD = int(env("FREE_SHIPPING_THRESHOLD", "300"))
FLAT_SHIPPING_RATE = int(env("FLAT_SHIPPING_RATE", "15"))
