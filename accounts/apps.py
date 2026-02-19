"""
Конфигурация приложения accounts.
"""
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Конфигурация приложения accounts."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Управление пользователями"

    def ready(self):
        """Подключает сигналы при запуске приложения."""
        import accounts.signals  # noqa: F401
