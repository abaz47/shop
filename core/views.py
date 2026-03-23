from types import SimpleNamespace

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import render

from .context_processors import FOOTER_LEGAL_LINKS, HEADER_PAGE_LINKS
from .models import LegalPage

SLUG_TO_TITLE = dict(FOOTER_LEGAL_LINKS + HEADER_PAGE_LINKS)


def home(request):
    """Главная страница."""
    return render(request, "core/home.html")


def legal_page(request, slug):
    """Страница юридического/информационного контента по slug."""
    page = LegalPage.objects.filter(slug=slug).first()
    if page is None:
        if slug not in SLUG_TO_TITLE:
            raise Http404("Страница не найдена")
        page = SimpleNamespace(
            title=SLUG_TO_TITLE[slug],
            content="",
        )
    return render(request, "core/legal_page.html", {"page": page})


def robots_txt(request):
    """
    Отдаёт robots.txt для поисковых систем.
    Disallow: /admin/, /accounts/ (личные данные). Sitemap — по текущему хосту.
    """
    scheme = "https" if request.is_secure() else "http"
    host = request.get_host()
    sitemap_url = f"{scheme}://{host}/sitemap.xml"
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /accounts/",
        "Disallow: /orders/",
        "Disallow: /cart/",
        "",
        f"Sitemap: {sitemap_url}",
    ]
    return HttpResponse(
        "\n".join(lines),
        content_type="text/plain; charset=utf-8"
    )


def yandex_webmaster_verification(request, verification_key):
    """Отдаёт файл подтверждения Яндекс.Вебмастера по ключу из .env."""
    expected_key = settings.YANDEX_WEBMASTER_VERIFICATION_KEY
    if not expected_key or verification_key != expected_key:
        raise Http404("Файл подтверждения не найден")

    content = (
        "<html>\n"
        "  <head>\n"
        "    <meta http-equiv=\"Content-Type\" "
        "content=\"text/html; charset=UTF-8\">\n"
        "  </head>\n"
        f"  <body>Verification: {expected_key}</body>\n"
        "</html>"
    )
    return HttpResponse(content, content_type="text/html; charset=utf-8")


def google_search_console_verification(request, verification_key):
    """Отдаёт файл подтверждения Google Search Console по ключу из .env."""
    expected_key = settings.GOOGLE_SEARCH_CONSOLE_VERIFICATION_KEY
    if not expected_key or verification_key != expected_key:
        raise Http404("Файл подтверждения не найден")

    content = f"google-site-verification: google{expected_key}.html"
    return HttpResponse(content, content_type="text/plain; charset=utf-8")


def page_not_found(request, exception):
    """Кастомная страница 404."""
    return render(request, "core/404.html", status=404)


def server_error(request):
    """Кастомная страница 500."""
    return render(request, "core/500.html", status=500)
