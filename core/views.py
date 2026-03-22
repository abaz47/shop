from types import SimpleNamespace

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


def page_not_found(request, exception):
    """Кастомная страница 404."""
    return render(request, "core/404.html", status=404)


def server_error(request):
    """Кастомная страница 500."""
    return render(request, "core/500.html", status=500)
