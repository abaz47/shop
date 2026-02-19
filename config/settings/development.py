"""
Настройки для локальной разработки.
"""
import os

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

ACCOUNT_ACTIVATION_TIMEOUT = int(
    os.environ.get("ACCOUNT_ACTIVATION_TIMEOUT", "86400"),
)
