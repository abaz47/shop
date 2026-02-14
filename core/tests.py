"""
Тесты приложения core.
"""
import pytest
from django.urls import reverse

from core.models import LegalPage


@pytest.mark.django_db
class TestMainPageView:
    """Тесты главной страницы (каталог)."""

    def test_main_page_returns_200(self, client):
        """Главная страница (каталог) отвечает 200."""
        response = client.get(reverse("catalog:product_list"))
        assert response.status_code == 200

    def test_main_page_uses_correct_template(self, client):
        """Используется шаблон catalog/product_list.html."""
        response = client.get(reverse("catalog:product_list"))
        assert response.templates
        template_names = [t.name for t in response.templates]
        assert "catalog/product_list.html" in template_names

    def test_main_page_contains_site_title(self, client):
        """На странице есть название сайта из БД."""
        from core.models import SiteSettings
        obj, _ = SiteSettings.objects.get_or_create(
            key="main",
            defaults={"site_name": "Тестовый магазин", "site_description": ""},
        )
        obj.site_name = "Тестовый магазин"
        obj.save()
        response = client.get(reverse("catalog:product_list"))
        assert "Тестовый магазин" in response.content.decode()

    def test_main_page_footer_contains_legal_links(self, client):
        """В футере есть ссылки на юридические страницы."""
        response = client.get(reverse("catalog:product_list"))
        html = response.content.decode()
        assert "Пользовательское соглашение" in html
        assert "Политика конфиденциальности" in html
        assert "Оферта" in html
        assert "Реквизиты" in html
        assert "Возврат и обмен" in html

    def test_main_page_header_contains_page_links(self, client):
        """В шапке есть ссылки «Оплата и доставка» и «Контакты»."""
        response = client.get(reverse("catalog:product_list"))
        html = response.content.decode()
        assert "Оплата и доставка" in html
        assert "Контакты" in html


@pytest.mark.django_db
class TestLegalPageView:
    """Тесты страниц юридического контента."""

    def test_legal_page_returns_200_when_exists(self, client):
        """Страница по существующему slug возвращает 200."""
        LegalPage.objects.create(
            slug="terms",
            title="Пользовательское соглашение",
            content="<p>Текст соглашения.</p>",
        )
        response = client.get(reverse(
            "core:legal_page",
            kwargs={"slug": "terms"}
        ))
        assert response.status_code == 200
        assert "Пользовательское соглашение" in response.content.decode()
        assert "Текст соглашения" in response.content.decode()

    def test_legal_page_returns_404_when_not_found(self, client):
        """Несуществующий slug возвращает 404."""
        response = client.get(reverse(
            "core:legal_page",
            kwargs={"slug": "nonexistent"}
        ))
        assert response.status_code == 404

    def test_legal_page_shows_stub_when_no_record(self, client):
        """По slug без записи в БД показывается заглушка с заголовком."""
        response = client.get(reverse(
            "core:legal_page",
            kwargs={"slug": "privacy"}
        ))
        assert response.status_code == 200
        html = response.content.decode()
        assert "Политика конфиденциальности" in html
        assert "Страница в разработке" in html

    def test_header_page_stub(self, client):
        """Страница из шапки (Оплата и доставка) открывается заглушкой."""
        response = client.get(reverse(
            "core:legal_page",
            kwargs={"slug": "payment_delivery"}
        ))
        assert response.status_code == 200
        html = response.content.decode()
        assert "Оплата и доставка" in html
        assert "Страница в разработке" in html
