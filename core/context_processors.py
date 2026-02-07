"""
Контекст-процессоры для шаблонов.
"""
from django.conf import settings


def site(request):
    """Добавляет в контекст название и описание сайта из настроек."""
    return {
        "site_name": getattr(settings, "SITE_NAME", "Магазин"),
        "site_description": getattr(
            settings,
            "SITE_DESCRIPTION",
            "Интернет-магазин"
        ),
    }
