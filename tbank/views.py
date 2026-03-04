"""
Представления для интеграции с платежной формой T‑Банка.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from orders.models import Order

from .client import TbankClient, TbankAPIError, build_default_urls
from .utils import (
    build_receipt,
    make_tbank_order_id,
    parse_order_pk_from_tbank_id,
    verify_notification_token,
)

logger = logging.getLogger(__name__)


@login_required
@require_POST
def start_payment_view(request: HttpRequest, order_id: int) -> HttpResponse:
    """
    Запускает платёж по уже созданному заказу и редиректит на PaymentURL.
    """
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    if order.total <= 0:
        messages.error(request, "Неверная сумма заказа для оплаты.")
        return redirect("orders:success", order_id=order.pk)

    # Уникальный OrderId для T‑Банка: pk + timestamp.
    # Один и тот же order.pk нельзя использовать повторно — банк отклоняет.
    tbank_order_id = make_tbank_order_id(order.pk)
    client = TbankClient()
    urls = build_default_urls(request, str(order.pk))
    try:
        result = client.init_payment(
            order_id=tbank_order_id,
            amount=order.total,
            description=f"Оплата заказа #{order.pk}",
            customer_key=str(order.user_id) if order.user_id else None,
            success_url=urls["success_url"],
            fail_url=urls["fail_url"],
            notification_url=urls["notification_url"],
            extra_data={"order_number": str(order.pk)},
            receipt=build_receipt(order),
        )
    except TbankAPIError as exc:
        logger.exception(
            "T‑Bank start_payment_view error for order_id=%s "
            "tbank_order_id=%s response=%s",
            order.pk,
            tbank_order_id,
            exc.response,
        )
        messages.error(
            request,
            "Не удалось инициировать оплату в T‑Банке. "
            "Попробуйте позже или свяжитесь с нами.",
        )
        return redirect("orders:success", order_id=order.pk)

    if result.payment_id:
        order.tbank_payment_id = result.payment_id
        order.save(update_fields=["tbank_payment_id", "updated_at"])

    return redirect(result.payment_url)


@require_GET
def payment_success_view(request: HttpRequest, order_id: int) -> HttpResponse:
    """
    Страница успешно завершённой оплаты.

    Фактическое изменение статуса заказа выполняется по уведомлению
    NotificationURL; здесь только показываем состояние заказа.
    """
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    return render(
        request,
        "tbank/payment_success.html",
        {"order": order},
    )


@require_GET
def payment_fail_view(request: HttpRequest, order_id: int) -> HttpResponse:
    """
    Страница неуспешной оплаты.
    """
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    return render(
        request,
        "tbank/payment_fail.html",
        {"order": order},
    )


def _parse_notification_body(request: HttpRequest) -> dict[str, Any] | None:
    """
    Разбирает тело уведомления T‑Банка (JSON или form-urlencoded).

    Возвращает словарь payload или None, если тело не удалось распарсить.
    """
    raw_body = request.body.decode("utf-8", errors="ignore")

    if request.content_type and "application/json" in request.content_type:
        try:
            return json.loads(raw_body or "{}")
        except json.JSONDecodeError:
            logger.warning(
                "T‑Bank notification invalid JSON: body=%r", raw_body[:1000]
            )
            return None

    payload = request.POST.dict()
    if payload:
        return payload

    if raw_body:
        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            logger.warning(
                "T‑Bank notification empty POST and invalid JSON: "
                "content_type=%s body=%r",
                request.content_type,
                raw_body[:1000],
            )
    return None


def _apply_notification(
    order: Order,
    success_flag: bool,
    status: str,
    payment_id: str,
) -> None:
    """Обновляет заказ по данным из уведомления T‑Банка."""
    update_fields: list[str] = ["updated_at"]

    if payment_id and not order.tbank_payment_id:
        order.tbank_payment_id = payment_id
        update_fields.append("tbank_payment_id")

    if success_flag and status in {"AUTHORIZED", "CONFIRMED"}:
        if order.status != Order.Status.PAID:
            order.status = Order.Status.PAID
            update_fields.append("status")
        order.save(update_fields=update_fields)
    elif order.status == Order.Status.UNPAID:
        order.save(update_fields=update_fields)


@csrf_exempt
@require_POST
def notification_view(request: HttpRequest) -> HttpResponse:
    """
    Обработчик HTTP(S)-уведомлений T‑Банка (NotificationURL).

    Согласно документации:
    https://developer.tbank.ru/eacq/intro/developer/notification
    необходимо вернуть HTTP 200 OK c телом "OK" при успешной обработке.
    """
    _OK = HttpResponse("OK")

    payload = _parse_notification_body(request)
    if payload is None:
        return _OK

    logger.info(
        "T‑Bank notification received: payload=%s",
        {k: v for k, v in payload.items() if k != "Token"},
    )

    password = getattr(settings, "TBANK_PASSWORD", "")
    if not password:
        logger.error("TBANK_PASSWORD is not configured for notifications")
        return _OK
    if not verify_notification_token(payload, password):
        logger.warning(
            "T‑Bank notification invalid token for OrderId=%s",
            payload.get("OrderId"),
        )
        return _OK

    raw_order_id = str(payload.get("OrderId") or "").strip()
    if not raw_order_id:
        logger.warning("T‑Bank notification without OrderId: %s", payload)
        return _OK

    order_pk = parse_order_pk_from_tbank_id(raw_order_id)
    try:
        order = Order.objects.get(pk=order_pk)
    except (Order.DoesNotExist, ValueError):
        return _OK

    _apply_notification(
        order,
        success_flag=str(payload.get("Success") or "").lower() == "true",
        status=str(payload.get("Status") or "").upper(),
        payment_id=str(payload.get("PaymentId") or "").strip(),
    )
    return _OK
