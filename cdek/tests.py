"""
Тесты интеграции и сервисов CDEK.
"""
from decimal import Decimal

import pytest

from cdek.client import CdekAPIError, CdekClient
from cdek import services as cdek_services


class TestCdekClientHelpers:
    """Тесты вспомогательных методов клиента CDEK."""

    def test_packages_to_api_format_converts_mm_to_cm_and_clamps(self):
        packages = [
            {"weight": 0, "length": 0, "width": 5, "height": 15},
            {"weight": 1234, "length": 250, "width": 100, "height": 300},
        ]
        result = CdekClient._packages_to_api_format(packages)
        # Нули превращаются в 1, мм → см с округлением
        assert result == [
            {"weight": 1, "length": 1, "width": 1, "height": 2},
            {"weight": 1234, "length": 25, "width": 10, "height": 30},
        ]


class TestDeliverySumToDecimal:
    """Тесты преобразования delivery_sum в Decimal."""

    def test_delivery_sum_to_decimal_valid_number(self):
        data = {"delivery_sum": 123.45}
        result = cdek_services.delivery_sum_to_decimal(data)
        assert isinstance(result, Decimal)
        assert result == Decimal("123.45")

    def test_delivery_sum_to_decimal_missing_key(self):
        assert cdek_services.delivery_sum_to_decimal({}) == Decimal("0")

    def test_delivery_sum_to_decimal_invalid_type(self):
        assert cdek_services.delivery_sum_to_decimal({"delivery_sum": object()}) == Decimal("0")


@pytest.mark.django_db
class TestCalculateDeliveryAndTarifflist:
    """Тесты обёрток расчёта доставки / списка тарифов."""

    def test_calculate_delivery_returns_none_when_client_missing(self, settings, monkeypatch):
        """Если нет настроек CDEK, calculate_delivery возвращает None и не падает."""
        settings.CDEK_ACCOUNT = ""
        settings.CDEK_SECURE = ""
        result = cdek_services.calculate_delivery(
            from_city_code=137,
            to_city_code=44,
            packages=[],
        )
        assert result is None

    def test_calculate_delivery_handles_cdek_error(self, settings, monkeypatch):
        """Ошибки CDEK API перехватываются и возвращается None."""
        settings.CDEK_ACCOUNT = "test"
        settings.CDEK_SECURE = "secret"

        class DummyClient:
            def calculate_tariff(self, **kwargs):
                raise CdekAPIError("boom")

        monkeypatch.setattr(cdek_services, "get_client", lambda: DummyClient())
        result = cdek_services.calculate_delivery(
            from_city_code=137,
            to_city_code=44,
            packages=[{"weight": 500, "length": 100, "width": 100, "height": 100}],
        )
        assert result is None

    def test_calculate_tarifflist_flattens_response_shapes(self, settings, monkeypatch):
        """calculate_tarifflist корректно извлекает тарифы из разных форматов ответа."""
        settings.CDEK_ACCOUNT = "test"
        settings.CDEK_SECURE = "secret"

        class DummyClient:
            def __init__(self, payload):
                self._payload = payload

            def calculate_tariff_list(self, **kwargs):
                return self._payload

        # Вариант 1: ключ tariff_codes
        payload1 = {
            "tariff_codes": [
                {"tariff_code": 136, "tariff_name": "Посылка склад-склад"},
                137,
            ]
        }
        monkeypatch.setattr(
            cdek_services, "get_client", lambda: DummyClient(payload1)
        )
        result1 = cdek_services.calculate_tarifflist(137, 44, [])
        assert result1 == [
            {"tariff_code": 136, "tariff_name": "Посылка склад-склад"},
            {"tariff_code": 137},
        ]

        # Вариант 2: ключ tariffs
        payload2 = {
            "tariffs": [
                {
                    "tariff_code": 233,
                    "tariff_name": "Экономичная посылка склад-дверь",
                },
            ]
        }
        monkeypatch.setattr(
            cdek_services, "get_client", lambda: DummyClient(payload2)
        )
        result2 = cdek_services.calculate_tarifflist(137, 44, [])
        assert result2 == payload2["tariffs"]


@pytest.mark.django_db
class TestCitiesSearch:
    """Тесты кеширования и поиска городов CDEK."""

    def test_search_cities_uses_cached_cities(self, monkeypatch):
        cities = [
            {"code": 1, "city": "Москва", "region": "Московская область"},
            {"code": 2, "city": "Санкт-Петербург", "region": "Ленинградская область"},
        ]

        monkeypatch.setattr(
            cdek_services,
            "get_cities_cached",
            lambda: cities,
        )

        results = cdek_services.search_cities("петербург", limit=10)
        assert len(results) == 1
        assert results[0]["code"] == 2
        assert "Санкт-Петербург" in results[0]["city"]

