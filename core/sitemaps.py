"""
Sitemap для поисковых систем (каталог, главная).
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from catalog.models import Product


class ProductSitemap(Sitemap):
    """Карта товаров (одна страница на товар)."""
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return Product.objects.filter(is_active=True).order_by("-updated_at")

    def lastmod(self, obj):
        return obj.updated_at


class StaticSitemap(Sitemap):
    """Главная и каталог."""
    changefreq = "daily"
    priority = 1.0

    def items(self):
        return ["catalog:product_list"]

    def location(self, obj):
        return reverse(obj)
