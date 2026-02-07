"""
Модели для настроек сайта и юридических страниц (каркас магазина).
"""
from django.db import models


class SiteSettings(models.Model):
    """
    Настройки сайта (название, описание).
    """
    key = models.CharField(
        "Ключ",
        max_length=50,
        unique=True,
        default="main",
        editable=False,
    )
    site_name = models.CharField(
        "Название сайта",
        max_length=255,
        default="Магазин",
    )
    site_description = models.CharField(
        "Краткое описание",
        max_length=255,
        default="Интернет-магазин",
        blank=True,
    )

    class Meta:
        verbose_name = "настройки сайта"
        verbose_name_plural = "настройки сайта"

    def __str__(self):
        return self.site_name


class LegalPage(models.Model):
    """
    Юридические и информационные страницы.
    """
    SLUG_CHOICES = [
        ("terms", "Пользовательское соглашение"),
        ("privacy", "Политика конфиденциальности"),
        ("offer", "Оферта"),
        ("requisites", "Реквизиты"),
        ("return", "Возврат и обмен"),
    ]

    slug = models.SlugField(
        "Идентификатор (slug)",
        max_length=50,
        choices=SLUG_CHOICES,
        unique=True,
    )
    title = models.CharField("Заголовок страницы", max_length=255)
    content = models.TextField("Содержимое (HTML)", blank=True)

    class Meta:
        verbose_name = "юридическая страница"
        verbose_name_plural = "юридические страницы"
        ordering = ["slug"]

    def __str__(self):
        return self.title
