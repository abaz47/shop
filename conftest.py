"""
Общая конфигурация pytest для проекта.
"""
import os

import django
from django.conf import settings  # noqa: F401

# Убеждаемся, что тесты используют настройки разработки
if not os.environ.get("DJANGO_SETTINGS_MODULE"):
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE",
        "config.settings.development"
    )

django.setup()
