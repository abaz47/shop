"""
Тесты интеграции заказов с CDEK: API тарифов/городов и создание заказа.
"""
from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from cart.models import Cart, CartItem
from catalog.models import Category, Product
from orders import services as order_services
from orders import views as order_views
from orders.models import Order, OrderItem


pytestmark = pytest.mark.django_db


def _create_product() -> Product:
    category = Category.objects.create(name="Тест", slug="test", order=0)
    return Product.objects.create(
        name="Тестовый товар",
        category=category,
        price=1000,
        discount_percent=0,
        is_active=True,
        weight_g=500,
        length_mm=100,
        width_mm=100,
        height_mm=100,
    )


class TestTariffHelpers:
    """Тесты вспомогательных функций фильтрации тарифов."""

    def test_is_allowed_tariff_family_accepts_parcel_and_express(self):
        assert order_views._is_allowed_tariff_family("Посылка склад-склад")
        assert order_views._is_allowed_tariff_family(
            "экономичная посылка склад-постамат"
        )
        assert order_views._is_allowed_tariff_family("Экспресс склад-дверь")
        assert not order_views._is_allowed_tariff_family(
            "Какой-то другой тариф"
        )

    def test_tariff_kind_by_name_classifies_directions(self):
        assert order_views._tariff_kind_by_name(
            "Посылка склад-склад"
        ) == "office"
        assert order_views._tariff_kind_by_name(
            "Экономичная посылка склад-постамат"
        ) == "pickup"
        assert order_views._tariff_kind_by_name(
            "Посылка склад-дверь"
        ) == "door"
        # Неподходящие направления
        assert order_views._tariff_kind_by_name("Посылка дверь-дверь") is None
        assert order_views._tariff_kind_by_name("Посылка дверь-склад") is None

    def test_filter_tariffs_for_response_office_pvz_only_office(self):
        raw = [
            {
                "tariff_code": 136,
                "tariff_name": "Посылка склад-склад",
                "delivery_sum": 200,
            },
            {
                "tariff_code": 137,
                "tariff_name": "Посылка склад-дверь",
                "delivery_sum": 150,
            },
            {
                "tariff_code": 233,
                "tariff_name": "Экономичная посылка склад-постамат",
                "delivery_sum": 100,
            },
        ]
        # Для ПВЗ должны остаться только склад-склад
        filtered = order_views._filter_tariffs_for_response(
            raw,
            mode="office",
            point_type="PVZ"
        )
        assert len(filtered) == 1
        assert filtered[0]["tariff_code"] == 136

    def test_filter_tariffs_for_response_office_postamat_only_pickup(self):
        raw = [
            {
                "tariff_code": 136,
                "tariff_name": "Посылка склад-склад",
                "delivery_sum": 200,
            },
            {
                "tariff_code": 233,
                "tariff_name": "Экономичная посылка склад-постамат",
                "delivery_sum": 100,
            },
        ]
        filtered = order_views._filter_tariffs_for_response(
            raw, mode="office", point_type="POSTAMAT"
        )
        assert len(filtered) == 1
        assert filtered[0]["tariff_code"] == 233

    def test_filter_tariffs_for_response_door_only_courier(self):
        raw = [
            {
                "tariff_code": 136,
                "tariff_name": "Посылка склад-склад",
                "delivery_sum": 200,
            },
            {
                "tariff_code": 137,
                "tariff_name": "Посылка склад-дверь",
                "delivery_sum": 150,
            },
        ]
        filtered = order_views._filter_tariffs_for_response(
            raw,
            mode="door",
            point_type=""
        )
        assert len(filtered) == 1
        assert filtered[0]["tariff_code"] == 137


class TestCheckoutCitiesView:
    """Тесты API поиска городов CDEK."""

    def test_checkout_cities_requires_min_query_length(self, client):
        url = reverse("orders:checkout_cities")
        response = client.get(url, {"q": "а"})
        assert response.status_code == 200
        assert response.json() == {"cities": []}

    def test_checkout_cities_uses_search_cities_service(
        self,
        client,
        monkeypatch
    ):
        url = reverse("orders:checkout_cities")
        called = {}

        def fake_search(query: str, limit: int = 30):
            called["query"] = query
            called["limit"] = limit
            return [{"code": 1, "city": "Москва"}]

        monkeypatch.setattr(order_views, "search_cities", fake_search)
        response = client.get(url, {"q": "моск"})
        assert response.status_code == 200
        data = response.json()
        assert data["cities"] == [{"code": 1, "city": "Москва"}]
        assert called == {"query": "моск", "limit": 30}


class TestCheckoutTariffsView:
    """Тесты API тарифов CDEK по выбранному адресу / ПВЗ."""

    def _auth_client_with_cart(self, client):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="user",
            email="user@example.com",
            password="pass",
        )
        client.force_login(user)
        product = _create_product()
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        return user, cart

    def test_checkout_tariffs_requires_login(self, client):
        url = reverse("orders:checkout_tariffs")
        response = client.post(
            url,
            data=json.dumps({"mode": "office", "city_code": 1}),
            content_type="application/json",
        )
        # login_required → редирект на страницу логина
        assert response.status_code in {302, 301}

    def test_checkout_tariffs_returns_filtered_tariffs(
        self,
        client,
        monkeypatch,
        settings
    ):
        settings.CDEK_FROM_CITY_CODE = 137
        self._auth_client_with_cart(client)

        def fake_tarifflist(from_city_code, to_city_code, packages):
            assert from_city_code == 137
            assert to_city_code == 44
            assert len(packages) == 1
            return [
                {
                    "tariff_code": 136,
                    "tariff_name": "Посылка склад-склад",
                    "delivery_sum": 200,
                },
                {
                    "tariff_code": 233,
                    "tariff_name": "Экономичная посылка склад-постамат",
                    "delivery_sum": 150,
                },
            ]

        monkeypatch.setattr(
            order_views,
            "calculate_tarifflist",
            fake_tarifflist
        )

        url = reverse("orders:checkout_tariffs")
        body = {
            "mode": "office",
            "city_code": 44,
            "city": "",
            "point_type": "PVZ"
        }
        response = client.post(
            url,
            data=json.dumps(body),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["city_code"] == 44
        # Для ПВЗ должен остаться только склад-склад
        assert [t["tariff_code"] for t in data["tariffs"]] == [136]

    def test_checkout_tariffs_uses_city_name_when_code_missing(
        self,
        client,
        monkeypatch,
        settings
    ):
        settings.CDEK_FROM_CITY_CODE = 137
        self._auth_client_with_cart(client)

        def fake_search(name: str, limit: int = 1):
            return [{"code": 99}]

        def fake_tarifflist(from_city_code, to_city_code, packages):
            assert to_city_code == 99
            return []

        monkeypatch.setattr(order_views, "search_cities", fake_search)
        monkeypatch.setattr(
            order_views,
            "calculate_tarifflist",
            fake_tarifflist
        )

        url = reverse("orders:checkout_tariffs")
        body = {"mode": "office", "city": "Москва", "point_type": "PVZ"}
        response = client.post(
            url,
            data=json.dumps(body),
            content_type="application/json",
        )
        assert response.status_code == 200
        assert response.json() == {"tariffs": [], "city_code": 99}


class TestCreateCdekOrder:
    """Тесты регистрации заказа в CDEK (обёртка вокруг API)."""

    def _create_order_with_items(self) -> Order:
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="order-user",
            email="order@example.com",
            password="pass",
        )
        product = _create_product()
        order = Order.objects.create(
            user=user,
            status=Order.Status.NEW,
            delivery_method=Order.DeliveryMethod.CDEK,
            delivery_type=Order.DeliveryType.PICKUP,
            delivery_tariff_code=136,
            products_total="1000.00",
            delivery_cost="200.00",
            total="1200.00",
            recipient_name="Иванов Иван",
            recipient_phone="+79990000000",
            city_code=44,
            pvz_code="TESTPVZ",
            delivery_address="",
            comment="Комментарий",
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            price=product.discounted_price,
            quantity=1,
        )
        return order

    def test_create_cdek_order_returns_none_when_client_missing(
        self,
        settings,
        caplog
    ):
        settings.CDEK_ACCOUNT = ""
        settings.CDEK_SECURE = ""
        order = self._create_order_with_items()
        uuid = order_services.create_cdek_order(order)
        assert uuid is None

    def test_create_cdek_order_sends_payload_to_client(
        self,
        settings,
        monkeypatch
    ):
        settings.CDEK_ACCOUNT = "test"
        settings.CDEK_SECURE = "secret"
        settings.CDEK_FROM_PVZ_CODE = "FROMPVZ"
        settings.CDEK_SENDER_NAME = "Отправитель"
        settings.CDEK_SENDER_PHONE = "+79990000001"
        settings.CDEK_SENDER_COMPANY = "ООО Тест"

        order = self._create_order_with_items()

        calls = {}

        class DummyClient:
            def create_order(self, **kwargs):
                calls["kwargs"] = kwargs
                return {
                    "entity": {"uuid": "cdek-uuid-123"},
                    "requests": [],
                }

        monkeypatch.setattr(
            order_services,
            "get_client",
            lambda: DummyClient()
        )
        uuid = order_services.create_cdek_order(order)
        assert uuid == "cdek-uuid-123"
        assert calls["kwargs"]["number"] == str(order.pk)
        assert calls["kwargs"]["tariff_code"] == order.delivery_tariff_code
        assert calls["kwargs"]["shipment_point"] == "FROMPVZ"
        assert calls["kwargs"]["recipient_name"] == order.recipient_name
        assert calls["kwargs"]["recipient_phone"] == order.recipient_phone
        # Для ПВЗ используется delivery_point, а не to_address
        assert calls["kwargs"]["delivery_point"] == order.pvz_code
        assert calls["kwargs"]["to_city_code"] is None
        assert calls["kwargs"]["to_address"] is None
