"""
Сервисы для работы с заказами: регистрация заказов в СДЭК.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings

from cdek.client import CdekAPIError
from cdek.services import (
    DEFAULT_HEIGHT_MM,
    DEFAULT_LENGTH_MM,
    DEFAULT_WEIGHT_G,
    DEFAULT_WIDTH_MM,
    get_client,
)

if TYPE_CHECKING:
    from orders.models import Order

logger = logging.getLogger(__name__)


def _build_packages_with_items(order: Order) -> list[dict]:
    """
    Формирует список грузовых мест с описанием товаров для POST /v2/orders.
    Структура пакетов совпадает с cart_items_to_packages, но дополнена items[].
    Размеры в сантиметрах (целые), вес в граммах.
    """
    packages = []
    pkg_num = 1
    for item in order.items.select_related("product"):
        product = item.product
        weight_g = product.weight_g or DEFAULT_WEIGHT_G
        length_mm = product.length_mm or DEFAULT_LENGTH_MM
        width_mm = product.width_mm or DEFAULT_WIDTH_MM
        height_mm = product.height_mm or DEFAULT_HEIGHT_MM

        weight = max(1, int(weight_g))
        length = max(1, round(length_mm / 10))
        width = max(1, round(width_mm / 10))
        height = max(1, round(height_mm / 10))

        item_payload = {
            "name": product.name[:255],
            "ware_key": str(product.pk)[:20],
            "payment": {"value": 0},
            "cost": float(item.price),
            "weight": weight,
            "amount": 1,
        }

        for _ in range(item.quantity):
            packages.append({
                "number": str(pkg_num),
                "weight": weight,
                "length": length,
                "width": width,
                "height": height,
                "items": [item_payload],
            })
            pkg_num += 1

    return packages


def _get_delivery_destination(
    order: Order,
) -> tuple[str | None, int | None, str | None]:
    """
    Возвращает (delivery_point, to_city_code, to_address) для create_order.
    Либо (pvz_code, None, None), либо (None, city_code, delivery_address).
    """
    from orders.models import Order as OrderModel

    if (
        order.delivery_type == OrderModel.DeliveryType.PICKUP
        and order.pvz_code
    ):
        return order.pvz_code, None, None
    if (
        order.delivery_type == OrderModel.DeliveryType.COURIER
        and order.delivery_address
    ):
        return None, order.city_code, order.delivery_address
    return None, None, None


def _parse_cdek_order_response(order_id: int, result: dict) -> str | None:
    """Из ответа POST /v2/orders извлекает UUID заказа или None при ошибке."""
    entity = result.get("entity") or {}
    cdek_uuid = (entity.get("uuid") or "").strip()

    requests_list = result.get("requests") or []
    if requests_list:
        req = requests_list[0]
        state = req.get("state", "")
        errors = req.get("errors") or []
        warnings = req.get("warnings") or []
        if warnings:
            logger.warning(
                "CDEK order %s registered with warnings: %s",
                order_id,
                warnings,
            )
        if errors:
            logger.error("CDEK order %s errors: %s", order_id, errors)
        if state == "INVALID":
            logger.error("CDEK rejected order %s (state=INVALID)", order_id)
            return None

    if not cdek_uuid:
        logger.error(
            "CDEK returned no uuid for order %s, full response: %s",
            order_id,
            result,
        )
        return None
    return cdek_uuid


def create_cdek_order(order: Order) -> str | None:
    """
    Регистрирует оформленный заказ в СДЭК через POST /v2/orders.

    Возвращает UUID заказа в СДЭК при успехе или None при ошибке.
    При ошибке заказ в нашей БД уже создан.

    :param order: Объект Order с уже сохранёнными полями и связанными items.
    """
    client = get_client()
    if not client:
        logger.warning(
            "CDEK client not configured — order %s not registered in CDEK",
            order.pk,
        )
        return None

    from_pvz_code = (getattr(settings, "CDEK_FROM_PVZ_CODE", "") or "").strip()
    if not from_pvz_code:
        logger.error(
            "CDEK_FROM_PVZ_CODE not set — order %s not registered in CDEK",
            order.pk,
        )
        return None

    sender_name = (
        getattr(settings, "CDEK_SENDER_NAME", "") or ""
    ).strip()
    sender_phone = (getattr(settings, "CDEK_SENDER_PHONE", "") or "").strip()
    sender_company = (
        getattr(settings, "CDEK_SENDER_COMPANY", "") or ""
    ).strip()

    packages = _build_packages_with_items(order)
    if not packages:
        logger.error(
            "No packages for order %s — order not registered in CDEK",
            order.pk,
        )
        return None

    delivery_point, to_city_code, to_address = _get_delivery_destination(order)
    if delivery_point is None and to_address is None:
        logger.error(
            "Cannot determine to_location for order %s "
            "(type=%s pvz=%s addr=%s)",
            order.pk,
            order.delivery_type,
            order.pvz_code,
            order.delivery_address,
        )
        return None

    try:
        result = client.create_order(
            number=str(order.pk),
            tariff_code=order.delivery_tariff_code,
            shipment_point=from_pvz_code,
            recipient_name=order.recipient_name,
            recipient_phone=order.recipient_phone,
            packages=packages,
            delivery_point=delivery_point,
            to_city_code=to_city_code,
            to_address=to_address,
            sender_name=sender_name,
            sender_phone=sender_phone,
            sender_company=sender_company,
            comment=order.comment,
        )
    except CdekAPIError as e:
        logger.error(
            "CDEK create_order API error for order %s: %s (body=%s)",
            order.pk,
            e,
            e.response,
        )
        return None

    cdek_uuid = _parse_cdek_order_response(order.pk, result)
    if cdek_uuid:
        logger.info(
            "Order %s registered in CDEK, uuid=%s", order.pk, cdek_uuid
        )
    return cdek_uuid


def _tracking_from_dict(obj: dict) -> str | None:
    """Извлекает трек-номер из словаря (cdek_number или delivery_number)."""
    if not isinstance(obj, dict):
        return None
    value = (
        obj.get("cdek_number") or obj.get("delivery_number") or ""
    ).strip()
    return value or None


def _tracking_from_related_entities(data: dict, entity: dict) -> str | None:
    """Ищет трек-номер в related_entities ответа СДЭК."""
    related = (
        data.get("related_entities")
        or entity.get("related_entities")
        or []
    )
    for rel in related:
        tracking = _tracking_from_dict(rel) if isinstance(rel, dict) else None
        if tracking:
            return tracking
    return None


def _tracking_from_delivery_detail(entity: dict) -> str | None:
    """Ищет трек-номер в delivery_detail ответа СДЭК."""
    delivery_detail = entity.get("delivery_detail") or []
    if not isinstance(delivery_detail, list) or not delivery_detail:
        return None
    first = delivery_detail[0]
    return _tracking_from_dict(first) if isinstance(first, dict) else None


def get_cdek_tracking_number(order: "Order") -> str | None:
    """
    Возвращает трек-номер СДЭК для заказа по cdek_order_uuid или None.
    """
    from cdek.services import get_client

    uuid = (order.cdek_order_uuid or "").strip()
    if not uuid:
        return None
    client = get_client()
    if not client:
        return None
    try:
        data = client.get_order(uuid)
    except CdekAPIError:
        return None
    entity = data.get("entity") or data
    return (
        _tracking_from_dict(entity)
        or _tracking_from_related_entities(data, entity)
        or _tracking_from_delivery_detail(entity)
    )
