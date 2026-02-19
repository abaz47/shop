"""
Контекст-процессоры для шаблонов.
"""
from django.contrib.sites.shortcuts import get_current_site

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


def site(request):
    """
    Добавляет в контекст название сайта из Django Sites
    и список ссылок на юридические страницы для футера.
    """
    try:
        current_site = get_current_site(request)
        site_name = current_site.name
    except Exception:
        site_name = "Магазин"

    return {
        "site_name": site_name,
        "footer_legal_links": FOOTER_LEGAL_LINKS,
        "header_page_links": HEADER_PAGE_LINKS,
    }
