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

HEADER_PAGE_SLUGS = {slug for slug, _ in HEADER_PAGE_LINKS}


def _get_active_nav(request):
    """
    Определяет, какой пункт верхнего меню активен.

    Возвращает кортеж:
    (active_nav, active_header_slug)
    """
    resolver_match = getattr(request, "resolver_match", None)
    if resolver_match is None:
        return "", ""

    view_name = resolver_match.view_name or ""
    kwargs = resolver_match.kwargs or {}

    active_nav = ""
    active_header_slug = ""

    # Любые страницы каталога (список, категории, карточка товара)
    if view_name.startswith("catalog:"):
        active_nav = "catalog"

    # Юридические/информационные страницы
    if view_name == "core:legal_page":
        slug = kwargs.get("slug")
        if slug in HEADER_PAGE_SLUGS:
            active_header_slug = slug

    return active_nav, active_header_slug


def site(request):
    """
    Добавляет базовые данные сайта в контекст:
    - название сайта из Django Sites;
    - ссылки футера и хэдера;
    - информацию об активных пунктах меню;
    - категории каталога для мобильного меню.
    """
    try:
        current_site = get_current_site(request)
        site_name = current_site.name
    except Exception:
        site_name = "Магазин"

    active_nav, active_header_slug = _get_active_nav(request)

    # Получаем категории для мобильного меню
    root_categories = None
    current_category = None
    open_accordion_ids = []

    try:
        from catalog.models import Category

        root_categories = Category.objects.filter(
            parent__isnull=True,
        ).prefetch_related("children")

        # Определяем текущую категорию, если мы на странице каталога
        resolver_match = getattr(request, "resolver_match", None)
        if resolver_match:
            view_name = resolver_match.view_name or ""
            kwargs = resolver_match.kwargs or {}

            if view_name.startswith("catalog:"):
                # Если есть slug в kwargs, значит мы на странице категории
                slug = kwargs.get("slug")
                if slug:
                    try:
                        current_category = Category.objects.prefetch_related(
                            "children"
                        ).get(slug=slug)
                        ancestors = current_category.get_ancestors()
                        root_pk = (
                            ancestors[0].pk if ancestors
                            else current_category.pk
                        )
                        open_accordion_ids = [root_pk]
                    except Category.DoesNotExist:
                        pass
    except ImportError:
        # Если приложение catalog не установлено, просто пропускаем
        pass

    return {
        "site_name": site_name,
        "footer_legal_links": FOOTER_LEGAL_LINKS,
        "header_page_links": HEADER_PAGE_LINKS,
        "active_nav": active_nav,
        "active_header_slug": active_header_slug,
        "root_categories": root_categories,
        "current_category": current_category,
        "open_accordion_ids": open_accordion_ids,
    }
