"""
Клиент для работы с платежной формой T‑Банка (eacq).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

import requests
from django.conf import settings
from django.urls import reverse

from .utils import build_token

logger = logging.getLogger(__name__)


class TbankAPIError(Exception):
    """Ошибка вызова API T‑Банка."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response: Mapping[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.response = dict(response or {})
        super().__init__(message)


@dataclass
class InitPaymentResult:
    """Результат вызова /v2/Init."""

    payment_url: str
    payment_id: str


class TbankClient:
    """
    Минимальный клиент T‑Банка для сценария redirect на PaymentURL.
    """

    def __init__(self) -> None:
        self.terminal_key: str = getattr(settings, "TBANK_TERMINAL_KEY", "")
        self.password: str = getattr(settings, "TBANK_PASSWORD", "")
        self.base_url: str = getattr(
            settings,
            "TBANK_API_BASE_URL",
            "https://securepay.tinkoff.ru",
        )
        self.timeout: int = int(getattr(settings, "TBANK_TIMEOUT", 15))

        if not self.terminal_key:
            raise TbankAPIError("Не задан TBANK_TERMINAL_KEY в настройках")
        if not self.password:
            raise TbankAPIError("Не задан TBANK_PASSWORD в настройках")

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"

    def _post(
        self,
        path: str,
        payload: dict[str, Any],
        error_message: str,
    ) -> dict[str, Any]:
        """Выполняет POST-запрос и возвращает тело ответа в виде словаря."""
        try:
            response = requests.post(
                self._url(path),
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            logger.exception("%s: %s", error_message, exc)
            raise TbankAPIError(
                error_message,
                status_code=getattr(
                    getattr(exc, "response", None), "status_code", None
                ),
            ) from exc

    def _build_init_payload(
        self,
        *,
        order_id: str,
        amount_kopeks: int,
        description: str,
        customer_key: str | None,
        success_url: str | None,
        fail_url: str | None,
        notification_url: str | None,
        extra_data: Mapping[str, str] | None,
        receipt: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "TerminalKey": self.terminal_key,
            "Amount": amount_kopeks,
            "OrderId": str(order_id),
        }
        if description:
            payload["Description"] = description[:140]
        if customer_key:
            payload["CustomerKey"] = str(customer_key)[:36]
        if success_url:
            payload["SuccessURL"] = success_url
        if fail_url:
            payload["FailURL"] = fail_url
        if notification_url:
            payload["NotificationURL"] = notification_url
        if extra_data:
            payload["DATA"] = dict(extra_data)
        if receipt:
            payload["Receipt"] = dict(receipt)
        return payload

    def init_payment(
        self,
        *,
        order_id: str,
        amount: Decimal,
        description: str = "",
        customer_key: str | None = None,
        success_url: str | None = None,
        fail_url: str | None = None,
        notification_url: str | None = None,
        extra_data: Mapping[str, str] | None = None,
        receipt: Mapping[str, Any] | None = None,
    ) -> InitPaymentResult:
        """
        Инициирует платёж и возвращает PaymentURL + PaymentId для редиректа.

        :param order_id: Уникальный OrderId для T‑Банка (pk + timestamp).
        :param amount: Сумма заказа в рублях.
        :param receipt: Объект Receipt для фискализации (54-ФЗ).
                        Формируется через tbank.utils.build_receipt(order).
        """
        if amount <= 0:
            raise ValueError("Сумма платежа должна быть положительной")

        amount_kopeks = int((amount * Decimal("100")).quantize(Decimal("1")))
        payload = self._build_init_payload(
            order_id=order_id,
            amount_kopeks=amount_kopeks,
            description=description,
            customer_key=customer_key,
            success_url=success_url,
            fail_url=fail_url,
            notification_url=notification_url,
            extra_data=extra_data,
            receipt=receipt,
        )
        payload["Token"] = build_token(payload, self.password)

        logger.info(
            "T‑Bank Init payment: order_id=%s amount_kopeks=%s payload=%s",
            order_id,
            amount_kopeks,
            {k: v for k, v in payload.items() if k != "Token"},
        )
        data = self._post(
            "/v2/Init",
            payload,
            "Не удалось инициировать платёж в T‑Банке"
        )
        logger.info("T‑Bank Init response: body=%s", data)

        payment_url = data.get("PaymentURL") or data.get("PaymentUrl")
        if not bool(data.get("Success")) or not payment_url:
            raise TbankAPIError(
                "Ошибка инициации платежа в T‑Банке",
                response=data
            )
        return InitPaymentResult(
            payment_url=str(payment_url),
            payment_id=str(data.get("PaymentId") or ""),
        )

    def cancel_payment(
        self,
        *,
        payment_id: str,
        amount: Decimal | None = None,
    ) -> dict[str, Any]:
        """
        Отменяет платёж через /v2/Cancel.

        Документация: https://developer.tbank.ru/eacq/api/cancel

        :param payment_id: PaymentId, полученный при инициации платежа.
        :param amount: Частичная сумма возврата в рублях.
                       Если не передана, отменяется вся сумма.
        :returns: Словарь с ответом T‑Банка.
        :raises TbankAPIError: При ошибке сети или если Success == false.
        """
        payload: dict[str, Any] = {
            "TerminalKey": self.terminal_key,
            "PaymentId": str(payment_id),
        }
        if amount is not None:
            payload["Amount"] = int(
                (amount * Decimal("100")).quantize(Decimal("1"))
            )
        payload["Token"] = build_token(payload, self.password)

        logger.info(
            "T‑Bank Cancel payment: payment_id=%s payload=%s",
            payment_id,
            {k: v for k, v in payload.items() if k != "Token"},
        )
        data = self._post(
            "/v2/Cancel",
            payload,
            "Не удалось отменить платёж в T‑Банке"
        )
        logger.info("T‑Bank Cancel response: body=%s", data)

        if not bool(data.get("Success")):
            raise TbankAPIError(
                "T‑Банк отклонил отмену платежа",
                response=data
            )
        return data


def build_default_urls(request, order_id: str) -> dict[str, str]:
    """
    Строит SuccessURL/FailURL/NotificationURL для указанного заказа.
    После оплаты пользователь попадает на страницу заказа с параметром
    payment=success или payment=fail.
    """
    base = request.build_absolute_uri(
        reverse("orders:success", kwargs={"order_id": order_id})
    )
    success_url = f"{base}?payment=success"
    fail_url = f"{base}?payment=fail"
    notification_url = request.build_absolute_uri(
        reverse("tbank:notification")
    )
    return {
        "success_url": success_url,
        "fail_url": fail_url,
        "notification_url": notification_url,
    }
