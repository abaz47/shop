"""
Тесты интеграции с T‑Банком.
"""
from decimal import Decimal
from unittest import mock

from django.urls import reverse
import pytest

from orders.models import Order

from .client import TbankClient
from .utils import (
    build_receipt,
    build_token,
    make_tbank_order_id,
    parse_order_pk_from_tbank_id,
    verify_notification_token,
)


def test_build_token_matches_docs_example():
    """
    Пример из документации T‑Банка:
    https://developer.tbank.ru/eacq/intro/developer/token
    """
    payload = {
        "Amount": "19200",
        "Description": "Подарочная карта на 1000 рублей",
        "OrderId": "00000",
        "TerminalKey": "MerchantTerminalKey",
    }
    password = "11111111111111"
    token = build_token(payload, password)
    assert (
        token
        == "72dd466f8ace0a37a1f740ce5fb78101712bc0665d91a8108c7c8a0ccd426db2"
    )


def test_verify_notification_token_roundtrip():
    """Проверка, что verify_notification_token валидирует корректный токен."""
    payload = {
        "TerminalKey": "1234567890DEMO",
        "OrderId": "000000",
        "Success": "true",
        "Status": "AUTHORIZED",
        "PaymentId": "0000000",
        "ErrorCode": "0",
        "Amount": "1111",
        "CardId": "000000",
        "Pan": "200000******0000",
        "ExpDate": "1111",
        "RebillId": "000000",
    }
    password = "11111111111"
    payload["Token"] = build_token(payload, password)
    assert verify_notification_token(payload, password) is True


def test_verify_notification_token_docs_example():
    """
    Проверяет эталонный пример из документации T‑Банка:
    https://developer.tbank.ru/eacq/intro/developer/notification
    """
    payload = {
        "TerminalKey": "1234567890DEMO",
        "OrderId": "000000",
        "Success": "true",
        "Status": "AUTHORIZED",
        "PaymentId": "0000000",
        "ErrorCode": "0",
        "Amount": "1111",
        "CardId": "000000",
        "Pan": "200000******0000",
        "ExpDate": "1111",
        "RebillId": "000000",
    }
    password = "11111111111"
    token = build_token(payload, password)
    assert (
        token
        == "1c0964277d0213349243065a0d5b838b8e90d2d25f740d0f2767836e710e80c8"
    )


def test_build_token_bool_is_lowercase():
    """
    Python-парсер JSON возвращает True/False (bool), тогда как T‑Банк
    вычисляет токен по строкам "true"/"false". Убедимся, что build_token
    корректно конвертирует bool → lowercase-строку.
    """
    payload_str = {
        "Success": "true",
        "TerminalKey": "DEMO",
        "Amount": "100",
    }
    payload_bool = {
        "Success": True,   # JSON-парсер даст bool
        "TerminalKey": "DEMO",
        "Amount": "100",
    }
    password = "secret"
    assert build_token(
        payload_str, password
    ) == build_token(payload_bool, password)


def test_make_tbank_order_id_contains_pk():
    """make_tbank_order_id начинается с pk заказа."""
    result = make_tbank_order_id(42)
    assert result.startswith("42-")
    parts = result.split("-")
    assert len(parts) == 2
    assert parts[0] == "42"
    assert parts[1].isdigit()


def test_parse_order_pk_simple():
    """parse_order_pk_from_tbank_id корректно разбирает «<pk>»."""
    assert parse_order_pk_from_tbank_id("11") == "11"


def test_parse_order_pk_with_timestamp():
    """parse_order_pk_from_tbank_id корректно разбирает «<pk>-<ts>»."""
    assert parse_order_pk_from_tbank_id("11-1709472000") == "11"


def test_parse_order_pk_empty():
    """parse_order_pk_from_tbank_id
    возвращает пустую строку при пустом входе.
    """
    assert parse_order_pk_from_tbank_id("") == ""


def test_make_and_parse_roundtrip():
    """make_tbank_order_id → parse_order_pk_from_tbank_id даёт исходный pk."""
    pk = 99
    tbank_id = make_tbank_order_id(pk)
    recovered = parse_order_pk_from_tbank_id(tbank_id)
    assert recovered == str(pk)


@mock.patch("tbank.client.requests.post")
def test_tbank_client_init_payment_success(mock_post, settings):
    """Клиент корректно формирует запрос и возвращает PaymentURL."""
    settings.TBANK_TERMINAL_KEY = "123456"
    settings.TBANK_PASSWORD = "secret"

    mock_post.return_value.status_code = 200
    mock_post.return_value.json.return_value = {
        "Success": True,
        "PaymentURL": "https://pay.example.com/payment",
    }

    client = TbankClient()
    tbank_order_id = make_tbank_order_id(1)
    url = client.init_payment(
        order_id=tbank_order_id,
        amount=Decimal("1000.00")
    )

    assert url == "https://pay.example.com/payment"
    assert mock_post.call_count == 1
    args, kwargs = mock_post.call_args
    assert args[0].endswith("/v2/Init")
    body = kwargs["json"]
    assert body["TerminalKey"] == "123456"
    assert body["Amount"] == 100000
    # OrderId должен содержать pk и timestamp-суффикс.
    assert body["OrderId"].startswith("1-")
    # Token должен быть вычислен и присутствовать.
    assert "Token" in body


def test_notification_view_updates_order_status(client, db, settings):
    """Уведомление AUTHORIZED/Success=True переводит заказ в статус PAID."""
    settings.TBANK_PASSWORD = "notify-secret"

    order = Order.objects.create(
        user=None,
        status=Order.Status.UNPAID,
        delivery_method=Order.DeliveryMethod.CDEK,
        delivery_type=Order.DeliveryType.PICKUP,
        products_total=Decimal("1000.00"),
        delivery_cost=Decimal("0.00"),
        total=Decimal("1000.00"),
        recipient_name="Тестовый Пользователь",
        recipient_phone="+79990000000",
        recipient_email="test@example.com",
    )

    from .utils import build_token as _build_token

    # Уведомление приходит с уникальным OrderId «<pk>-<ts>».
    tbank_order_id = make_tbank_order_id(order.pk)
    payload = {
        "TerminalKey": "123456",
        "OrderId": tbank_order_id,
        "Success": "true",
        "Status": "AUTHORIZED",
        "PaymentId": "111",
        "ErrorCode": "0",
        "Amount": "100000",
    }
    payload["Token"] = _build_token(payload, settings.TBANK_PASSWORD)

    url = reverse("tbank:notification")
    response = client.post(
        url,
        data=payload,
        content_type="application/json",
    )
    assert response.status_code == 200
    order.refresh_from_db()
    assert order.status == Order.Status.PAID


@pytest.mark.django_db
def test_build_receipt_structure(settings):
    """build_receipt формирует корректную структуру чека."""
    from decimal import Decimal
    from unittest import mock

    settings.TBANK_TAXATION = "usn_income"
    settings.TBANK_VAT_RATE = "none"
    settings.TBANK_DELIVERY_VAT_RATE = "none"

    product = mock.MagicMock()
    product.name = "Тестовый товар"
    variant = mock.MagicMock()
    variant.product = product

    item = mock.MagicMock()
    item.variant = variant
    item.price = Decimal("500.00")
    item.quantity = 2

    order = mock.MagicMock()
    order.recipient_email = "test@example.com"
    order.recipient_phone = ""
    order.delivery_cost = Decimal("300.00")
    order.items.select_related.return_value.all.return_value = [item]

    receipt = build_receipt(order)

    assert receipt["Taxation"] == "usn_income"
    assert receipt["Email"] == "test@example.com"
    assert len(receipt["Items"]) == 2  # товар + доставка

    good = receipt["Items"][0]
    assert good["Name"] == "Тестовый товар"
    assert good["Price"] == 50000       # 500 руб. в копейках
    assert good["Quantity"] == 2
    assert good["Amount"] == 100000     # 1000 руб. в копейках
    assert good["Tax"] == "none"
    assert good["PaymentMethod"] == "full_payment"
    assert good["PaymentObject"] == "commodity"

    delivery = receipt["Items"][1]
    assert delivery["Name"] == "Доставка"
    assert delivery["Price"] == 30000
    assert delivery["Amount"] == 30000
    assert delivery["PaymentObject"] == "service"


@pytest.mark.django_db
def test_build_receipt_no_delivery(settings):
    """build_receipt не добавляет строку доставки, если стоимость 0."""
    from decimal import Decimal
    from unittest import mock

    settings.TBANK_TAXATION = "usn_income"
    settings.TBANK_VAT_RATE = "vat0"
    settings.TBANK_DELIVERY_VAT_RATE = "vat0"

    product = mock.MagicMock()
    product.name = "Ещё один товар"
    variant = mock.MagicMock()
    variant.product = product

    item = mock.MagicMock()
    item.variant = variant
    item.price = Decimal("1000.00")
    item.quantity = 1

    order = mock.MagicMock()
    order.recipient_email = ""
    order.recipient_phone = "+79001234567"
    order.delivery_cost = Decimal("0")
    order.items.select_related.return_value.all.return_value = [item]

    receipt = build_receipt(order)

    assert receipt.get("Phone") == "+79001234567"
    assert "Email" not in receipt
    assert len(receipt["Items"]) == 1
