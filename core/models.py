"""
Модели для юридических страниц и изображений сайта.
"""
from django.db import models


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
        ("payment", "Оплата"),
        ("delivery", "Доставка"),
        ("contacts", "Контакты"),
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


class SiteImage(models.Model):
    """
    Изображения для использования на сайте (логотипы, иконки и т.д.).
    """
    CATEGORY_CHOICES = [
        ("payment", "Оплата (логотипы платежных систем)"),
        ("delivery", "Доставка (логотипы служб доставки)"),
        ("other", "Прочее"),
    ]

    name = models.CharField("Название", max_length=200)
    slug = models.SlugField(
        "Slug (для ссылки)",
        max_length=200,
        unique=True,
        help_text="Используется для получения ссылки на изображение",
    )
    image = models.ImageField(
        "Файл изображения",
        upload_to="site_images/%Y/%m/",
    )
    category = models.CharField(
        "Категория",
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="other",
    )
    description = models.TextField("Описание", blank=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        verbose_name = "изображение сайта"
        verbose_name_plural = "изображения сайта"
        ordering = ["category", "name"]

    def __str__(self):
        return self.name

    def get_url(self):
        """Возвращает URL изображения для использования в HTML."""
        return self.image.url
