"""
Контекст-процессоры для шаблонов.
"""
from django.db import OperationalError

# Ссылки футера
FOOTER_LEGAL_LINKS = [
    ("terms", "Пользовательское соглашение"),
    ("privacy", "Политика конфиденциальности"),
    ("offer", "Оферта"),
    ("requisites", "Реквизиты"),
    ("return", "Возврат и обмен"),
]

# Ссылки хэдера
HEADER_PAGE_LINKS = [
    ("payment", "Оплата"),
    ("delivery", "Доставка"),
    ("contacts", "Контакты"),
]

DEFAULT_SITE_NAME = "Магазин"
DEFAULT_SITE_DESCRIPTION = "Интернет-магазин"


def site(request):
    """
    Добавляет в контекст название и описание сайта из БД
    и список ссылок на юридические страницы для футера.
    """
    site_name = DEFAULT_SITE_NAME
    site_description = DEFAULT_SITE_DESCRIPTION

    try:
        from .models import SiteSettings
        obj = SiteSettings.objects.filter(key="main").first()
        if obj is None:
            obj = SiteSettings.objects.create(
                key="main",
                site_name=site_name,
                site_description=site_description,
            )
        site_name = obj.site_name
        site_description = obj.site_description or site_description
    except OperationalError:
        pass

    return {
        "site_name": site_name,
        "site_description": site_description,
        "footer_legal_links": FOOTER_LEGAL_LINKS,
        "header_page_links": HEADER_PAGE_LINKS,
    }
