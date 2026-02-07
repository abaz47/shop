"""
Тесты настроек проекта.
"""
import pytest  # noqa: F401


def test_debug_is_boolean():
    """DEBUG должен быть булевым."""
    from django.conf import settings
    assert isinstance(settings.DEBUG, bool)


def test_installed_apps_contains_core():
    """В INSTALLED_APPS есть core."""
    from django.conf import settings
    assert "core" in settings.INSTALLED_APPS


def test_staticfiles_dirs_configured():
    """STATICFILES_DIRS указывает на папку static."""
    from pathlib import Path
    from django.conf import settings
    base = settings.BASE_DIR
    assert any(base / "static" == Path(p) for p in settings.STATICFILES_DIRS)


def test_site_name_setting():
    """SITE_NAME задан."""
    from django.conf import settings
    assert hasattr(settings, "SITE_NAME")
    assert isinstance(settings.SITE_NAME, str)
    assert len(settings.SITE_NAME) > 0
