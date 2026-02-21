"""
Базовые настройки Django.
"""
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "django-insecure-change-me",
)

INSTALLED_APPS = [
    "accounts",
    "cart",
    "catalog",
    "core",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django_recaptcha",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
                "core.context_processors.site",
                "cart.context_processors.cart",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# PostgreSQL из DATABASE_URL
# (формат: postgresql://user:password@host:port/dbname)
_db_url = os.environ.get("DATABASE_URL", "")
if _db_url:
    _parsed = urlparse(_db_url)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _parsed.path[1:] or "shop_db",
            "USER": _parsed.username or "postgres",
            "PASSWORD": _parsed.password or "",
            "HOST": _parsed.hostname or "localhost",
            "PORT": str(_parsed.port or 5432),
            "OPTIONS": {"connect_timeout": 10},
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME":
            "django.contrib.auth."
            "password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME":
            "django.contrib.auth."
            "password_validation.MinimumLengthValidator"
    },
    {
        "NAME":
            "django.contrib.auth."
            "password_validation.CommonPasswordValidator"},
    {
        "NAME":
            "django.contrib.auth."
            "password_validation.NumericPasswordValidator"
    },
]

LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ID сайта для django.contrib.sites (по умолчанию 1)
SITE_ID = 1

# Настройки reCAPTCHA
RECAPTCHA_PUBLIC_KEY = os.environ.get("RECAPTCHA_PUBLIC_KEY", "")
RECAPTCHA_PRIVATE_KEY = os.environ.get("RECAPTCHA_PRIVATE_KEY", "")
RECAPTCHA_REQUIRED_SCORE = 0.85  # Порог для reCAPTCHA v3

# Настройки аутентификации
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/accounts/profile/"
LOGOUT_REDIRECT_URL = "/"
