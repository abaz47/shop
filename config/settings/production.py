"""
Настройки для продакшена.
"""
import os

from .base import *  # noqa: F401, F403

DEBUG = os.environ.get("DEBUG", "false").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

if not ALLOWED_HOSTS and not DEBUG:
    ALLOWED_HOSTS = ["localhost"]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Куки только по HTTPS
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Защита от XSS и MIME-sniffing
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
# HSTS (рекомендуется при работе только по HTTPS)
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Хранение файлов
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# Для корректной работы CSRF за обратным прокси/HTTPS
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

# Лимит загрузки файла в запросе
DATA_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024  # 25 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 25 * 1024 * 1024  # 25 MB

# Права на создаваемые при загрузке каталоги и файлы
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755
FILE_UPLOAD_PERMISSIONS = 0o644

# Логирование
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.core.mail": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "accounts.utils": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "tbank": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Email / SMTP
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")

EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "false").lower() == "true"

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# Настройка времени жизни ссылки активации аккаунта (секунды)
ACCOUNT_ACTIVATION_TIMEOUT = int(
    os.environ.get("ACCOUNT_ACTIVATION_TIMEOUT", "86400"),
)
