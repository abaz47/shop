"""
Утилиты для интеграции с T‑Банком (eacq).
"""
from __future__ import annotations

import hashlib
import time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:
    from orders.models import Order


def build_token(payload: Mapping[str, object], password: str) -> str:
    """
    Генерирует подпись Token для запросов к T‑Банку.

    Алгоритм соответствует документации:
    https://developer.tbank.ru/eacq/intro/developer/token
    """
    if not password:
        raise ValueError("Пароль T‑Банка (Password) не задан")

    # Берём только плоские поля корневого объекта, исключая Token.
    flat: dict[str, object] = {}
    for key, value in payload.items():
        if key == "Token":
            continue
        if isinstance(value, (dict, list, tuple, set)):
            continue
        flat[key] = value

    # Добавляем пароль.
    flat["Password"] = password

    # Сортируем по имени параметра.
    # bool конвертируем в lowercase-строку ("true"/"false"), как в примерах
    # документации T‑Банка, так как JSON-парсер Python возвращает True/False,
    # а T‑Банк вычисляет токен по строкам "true"/"false".
    parts: list[str] = []
    for key in sorted(flat):
        v = flat[key]
        if v is None:
            parts.append("")
        elif isinstance(v, bool):
            parts.append("true" if v else "false")
        else:
            parts.append(str(v))

    concatenated = "".join(parts)
    return hashlib.sha256(concatenated.encode("utf-8")).hexdigest()


def verify_notification_token(
    payload: Mapping[str, object],
    password: str,
) -> bool:
    """
    Проверяет подпись Token из уведомления T‑Банка.
    """
    token = str(payload.get("Token") or "")
    if not token:
        return False
    expected = build_token(payload, password)
    return token.lower() == expected.lower()


def _to_kopeks(amount: Decimal) -> int:
    """Конвертирует сумму в рублях в копейки (целое число)."""
    return int((amount * Decimal("100")).quantize(Decimal("1")))


def build_receipt(order: "Order") -> dict[str, Any]:
    """
    Формирует объект Receipt для метода /v2/Init по формату ФФД 1.05.

    Документация: https://developer.tbank.ru/eacq/scenarios/fiscalization/
    Параметры берутся из django.conf.settings:
      TBANK_TAXATION          — система налогообложения (usn_income, osn...)
      TBANK_VAT_RATE          — ставка НДС на товары (none, vat0, vat10, vat20)
      TBANK_DELIVERY_VAT_RATE — ставка НДС на доставку
    """
    from django.conf import settings

    taxation = getattr(settings, "TBANK_TAXATION", "usn_income")
    vat_rate = getattr(settings, "TBANK_VAT_RATE", "none")
    delivery_vat = getattr(settings, "TBANK_DELIVERY_VAT_RATE", "none")

    # Email или телефон обязателен согласно документации T‑Банка.
    email = (order.recipient_email or "").strip()
    phone = (order.recipient_phone or "").strip()

    receipt: dict[str, Any] = {
        "Taxation": taxation,
        "Items": [],
    }
    if email:
        receipt["Email"] = email
    elif phone:
        receipt["Phone"] = phone

    # Позиции товаров.
    for item in order.items.select_related("product").all():
        price_kopeks = _to_kopeks(item.price)
        amount_kopeks = _to_kopeks(item.price * item.quantity)
        receipt["Items"].append({
            "Name": item.product.name[:128],
            "Price": price_kopeks,
            "Quantity": item.quantity,
            "Amount": amount_kopeks,
            "Tax": vat_rate,
            "PaymentMethod": "full_payment",
            "PaymentObject": "commodity",
        })

    # Позиция доставки (если стоимость > 0).
    if order.delivery_cost and order.delivery_cost > 0:
        delivery_kopeks = _to_kopeks(order.delivery_cost)
        receipt["Items"].append({
            "Name": "Доставка",
            "Price": delivery_kopeks,
            "Quantity": 1,
            "Amount": delivery_kopeks,
            "Tax": delivery_vat,
            "PaymentMethod": "full_payment",
            "PaymentObject": "service",
        })

    return receipt


def make_tbank_order_id(order_pk: int) -> str:
    """
    Формирует уникальный OrderId для T‑Банка.

    Согласно документации T‑Банка, OrderId должен быть уникальным
    для каждой операции. Чтобы повторные попытки оплаты не падали
    с ошибкой «дублирующий OrderId», добавляем unix-timestamp.

    Формат: «<pk>-<ts>», например «11-1709472000».
    """
    return f"{order_pk}-{int(time.time())}"


def parse_order_pk_from_tbank_id(tbank_order_id: str) -> str:
    """
    Извлекает pk заказа из OrderId, отправленного в T‑Банк.

    Корректно обрабатывает оба формата:
    - «11»          → «11»  (старые заказы без суффикса)
    - «11-1709472000» → «11»
    """
    return tbank_order_id.split("-")[0] if tbank_order_id else ""
