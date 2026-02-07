"""
Тесты приложения core.
"""
import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestHomeView:
    """Тесты главной страницы."""

    def test_home_returns_200(self, client):
        """Главная страница отвечает 200."""
        response = client.get(reverse("core:home"))
        assert response.status_code == 200

    def test_home_uses_correct_template(self, client):
        """Используется шаблон core/home.html."""
        response = client.get(reverse("core:home"))
        assert response.templates
        template_names = [t.name for t in response.templates]
        assert "core/home.html" in template_names

    def test_home_contains_site_title(self, client):
        """На странице есть название сайта из настроек."""
        from django.conf import settings
        response = client.get(reverse("core:home"))
        assert settings.SITE_NAME in response.content.decode()
