"""
Сервисы расчёта доставки СДЭК по корзине.
Каждый товар — отдельная коробка; при quantity > 1 — несколько одинаковых мест.
"""
import logging
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.core.cache import cache

from .client import CdekAPIError, CdekClient, TARIFF_WAREHOUSE_DOOR

logger = logging.getLogger(__name__)

CITIES_CACHE_KEY = "cdek_cities_ru"
CITIES_CACHE_TIMEOUT = 86400  # 24 часа

# Дефолтные габариты и вес, если у товара не заданы (мм и г).
# СДЭК считает «вес к оплате» как максимальный
# из физического и объёмного = (Д×Ш×В см)/5000.
DEFAULT_WEIGHT_G = 500
DEFAULT_LENGTH_MM = 100
DEFAULT_WIDTH_MM = 100
DEFAULT_HEIGHT_MM = 100


def get_client() -> CdekClient | None:
    """Возвращает клиент СДЭК из настроек
    или None, если интеграция отключена.
    """
    account = getattr(settings, "CDEK_ACCOUNT", "") or ""
    secure = getattr(settings, "CDEK_SECURE", "") or ""
    if not account or not secure:
        return None
    test = getattr(settings, "CDEK_TEST", True)
    return CdekClient(account=account, secure=secure, test=test)


def cart_items_to_packages(cart_items) -> list[dict[str, int]]:
    """
    Преобразует позиции корзины в список грузовых мест для СДЭК.
    Один товар = одна коробка; при quantity > 1 — столько же одинаковых мест.

    :param cart_items:
        QuerySet или список CartItem с select_related("product").
    :return: Список словарей
        {"weight": г, "length": мм, "width": мм, "height": мм}.
    """
    packages = []
    for item in cart_items:
        product = item.product
        for _ in range(item.quantity):
            packages.append({
                "weight": product.weight_g or DEFAULT_WEIGHT_G,
                "length": product.length_mm or DEFAULT_LENGTH_MM,
                "width": product.width_mm or DEFAULT_WIDTH_MM,
                "height": product.height_mm or DEFAULT_HEIGHT_MM,
            })
    return packages


def _get_from_address() -> str:
    """Возвращает адрес ПВЗ отправки из настроек (CDEK_FROM_ADDRESS)."""
    return (getattr(settings, "CDEK_FROM_ADDRESS", "") or "").strip()


def calculate_delivery(
    from_city_code: int,
    to_city_code: int,
    packages: list[dict[str, int]],
    *,
    tariff_code: int = TARIFF_WAREHOUSE_DOOR,
) -> dict[str, Any] | None:
    """
    Рассчитывает стоимость и срок доставки СДЭК.

    :param from_city_code: Код города отправителя (СДЭК).
    :param to_city_code: Код города получателя (СДЭК).
    :param packages: Список грузовых мест
        (weight в г, length/width/height в мм).
    :param tariff_code: Код тарифа.
    :return:
        Словарь с delivery_sum (руб), period_min, period_max (дни)...,
        или None при ошибке.
    """
    client = get_client()
    if not client:
        logger.debug(
            "CDEK client not configured, skipping delivery calculation"
        )
        return None
    try:
        result = client.calculate_tariff(
            from_city_code=from_city_code,
            to_city_code=to_city_code,
            packages=packages,
            tariff_code=tariff_code,
            from_address=_get_from_address(),
        )
        return result
    except CdekAPIError as e:
        logger.warning("CDEK calculate_delivery failed: %s", e)
        return None


def calculate_tarifflist(
    from_city_code: int,
    to_city_code: int,
    packages: list[dict[str, int]],
) -> list[dict[str, Any]]:
    """
    Возвращает список тарифов СДЭК между городами (tarifflist).

    :param from_city_code: Код города отправителя (СДЭК). СПб = 137.
    :param to_city_code: Код города получателя (СДЭК).
    :param packages:
        Список грузовых мест (weight в г, length/width/height в мм).
    :return:
        Список тарифов с полями tariff_code, tariff_name, delivery_sum,
        period_min, period_max и др.
    """
    client = get_client()
    if not client:
        logger.debug(
            "CDEK client not configured, skipping tarifflist calculation"
        )
        return []
    try:
        data = client.calculate_tariff_list(
            from_city_code=from_city_code,
            to_city_code=to_city_code,
            packages=packages,
            from_address=_get_from_address(),
        )
    except CdekAPIError as e:
        logger.warning("CDEK calculate_tarifflist failed: %s", e)
        return []

    # Ответ API: массив тарифов может быть в tariff_codes, tariffs или в корне
    raw = data.get("tariff_codes") or data.get("tariffs")
    if raw is None and isinstance(data, list):
        raw = data
    if not isinstance(raw, list):
        logger.debug(
            "CDEK tarifflist unexpected response keys: %s",
            list(data.keys()) if isinstance(data, dict) else "not a dict"
        )
        return []
    # Элементы могут быть объектами с полями tariff_code, tariff_name и т.д.
    result = []
    for item in raw:
        if isinstance(item, dict):
            result.append(item)
        elif isinstance(item, (int, float)):
            result.append({"tariff_code": int(item)})
    return result


def get_cities_cached() -> list[dict]:
    """
    Список городов СДЭК (РФ), закэшированный на 24 часа.
    Возвращает список словарей с ключами code, city, region и др.
    """
    cities = cache.get(CITIES_CACHE_KEY)
    if cities is not None:
        return cities
    client = get_client()
    if not client:
        return []
    try:
        cities = client.get_cities(country_code="RU")
        if isinstance(cities, list):
            cache.set(CITIES_CACHE_KEY, cities, CITIES_CACHE_TIMEOUT)
            return cities
    except CdekAPIError as e:
        logger.warning("CDEK get_cities for cache failed: %s", e)
    return []


def search_cities(query: str, limit: int = 30) -> list[dict]:
    """
    Поиск городов по названию (по подстроке, без учёта регистра).
    Возвращает до limit совпадений с полями code, city, region.
    """
    if not query or not query.strip():
        return []
    q = query.strip().lower()
    cities = get_cities_cached()
    result = []
    for c in cities:
        city_name = (c.get("city") or c.get("name") or "").lower()
        region_name = (c.get("region") or "").lower()
        if q in city_name or q in region_name:
            try:
                code = int(c.get("code"))
            except (TypeError, ValueError):
                continue
            result.append({
                "code": code,
                "city": c.get("city") or c.get("name") or "",
                "region": c.get("region") or "",
            })
            if len(result) >= limit:
                break
    return result


def delivery_sum_to_decimal(data: dict[str, Any] | None) -> Decimal:
    """Из ответа калькулятора возвращает delivery_sum как Decimal или 0."""
    if not data or "delivery_sum" not in data:
        return Decimal("0")
    try:
        return Decimal(str(data["delivery_sum"]))
    except Exception:
        return Decimal("0")
