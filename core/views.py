from types import SimpleNamespace

from django.http import Http404
from django.shortcuts import render

from .context_processors import FOOTER_LEGAL_LINKS
from .models import LegalPage

SLUG_TO_TITLE = dict(FOOTER_LEGAL_LINKS)


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
