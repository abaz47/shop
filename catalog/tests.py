from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from .models import Category, Product, ProductVariant


class CatalogViewsTestCase(TestCase):
    """Тесты представлений каталога."""

    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(
            name="Тест",
            slug="test",
            order=0
        )
        self.product = Product.objects.create(
            name="Тестовый товар",
            category=self.category,
            is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            price=Decimal("1000.00"),
            discount_percent=Decimal("10.00"),
            is_active=True,
        )

    def test_product_list_returns_200(self):
        response = self.client.get(reverse("catalog:product_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Тестовый товар")
        self.assertContains(response, "900")

    def test_product_list_hides_inactive(self):
        self.product.is_active = False
        self.product.save()
        response = self.client.get(reverse("catalog:product_list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Тестовый товар")

    def test_product_detail_by_pk_returns_200(self):
        url = reverse(
            "catalog:product_detail",
            kwargs={"slug_or_pk": str(self.product.pk)},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Тестовый товар")
        self.assertContains(response, "900")
        self.assertContains(response, "1000")

    def test_product_detail_by_slug_returns_200(self):
        self.product.slug = "testovyj-tovar"
        self.product.save()
        response = self.client.get(
            reverse(
                "catalog:product_detail",
                kwargs={"slug_or_pk": "testovyj-tovar"},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Тестовый товар")

    def test_product_detail_404_for_inactive(self):
        self.product.is_active = False
        self.product.save()
        response = self.client.get(
            reverse(
                "catalog:product_detail",
                kwargs={"slug_or_pk": str(self.product.pk)},
            )
        )
        self.assertEqual(response.status_code, 404)
