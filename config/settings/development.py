"""
Настройки для локальной разработки.
"""
from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
]

# Для разработки письма выводятся в консоль, а не отправляются реально.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Локально можно всё равно читать значения из окружения для совместимости кода.
ACCOUNT_ACTIVATION_TIMEOUT = int(
    os.environ.get("ACCOUNT_ACTIVATION_TIMEOUT", "86400"),
)
