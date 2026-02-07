"""
Точка входа в настройки проекта.
По умолчанию загружаются настройки для разработки.
"""
import os

if os.environ.get("DJANGO_SETTINGS_MODULE") == "config.settings.production":
    from .production import *  # noqa: F401, F403
else:
    from .development import *  # noqa: F401, F403
