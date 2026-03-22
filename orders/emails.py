"""
Отправка писем о заказе.
Все письма с копией на ORDER_NOTIFICATION_EMAIL.
"""
import logging

from django.conf import settings
from django.template.loader import render_to_string
from django.urls import reverse

from accounts.utils import send_email_async

logger = logging.getLogger(__name__)


def _get_notification_bcc():
    """Список адресов для BCC (копия магазину)."""
    value = getattr(settings, "ORDER_NOTIFICATION_EMAIL", None)
    if not value:
        return []
    return [e.strip() for e in value.split(",") if e.strip()]


def _order_email_context(order, order_url=None):
    """Общий контекст для писем о заказе."""
    order.refresh_from_db()
    items = list(
        order.items.select_related("variant__product").order_by("id")
    )
    try:
        from django.contrib.sites.models import Site
        current_site = Site.objects.get_current()
        site_domain = current_site.domain
        site_name = current_site.name or "Интернет-магазин"
    except Exception:
        site_domain = (
            getattr(settings, "ALLOWED_HOSTS", []) or ["localhost"]
        )[0]
        site_name = "Интернет-магазин"
    if order_url is None:
        protocol = "https" if not settings.DEBUG else "http"
        order_path = reverse("orders:success", kwargs={"order_id": order.pk})
        order_url = f"{protocol}://{site_domain}{order_path}"
    return {
        "order": order,
        "items": items,
        "site_name": site_name,
        "order_url": order_url,
    }


def _send_order_email(order, subject, txt_tpl, html_tpl, context_extra=None):
    """Отправляет письмо о заказе клиенту и BCC на ORDER_NOTIFICATION_EMAIL."""
    bcc_list = _get_notification_bcc()
    recipient = (order.recipient_email or "").strip()
    if not recipient and not bcc_list:
        return
    context = _order_email_context(order)
    if context_extra:
        context.update(context_extra)
    message = render_to_string(txt_tpl, context)
    html_message = render_to_string(html_tpl, context)
    if recipient:
        to_list = [recipient]
        # BCC — копия магазину
    else:
        to_list = [bcc_list[0]] if bcc_list else []
        bcc_list = bcc_list[1:] if len(bcc_list) > 1 else []
    send_email_async(
        subject=subject,
        message=message,
        from_email=None,
        recipient_list=to_list,
        html_message=html_message,
        bcc=bcc_list if bcc_list else None,
    )
    logger.info("Письмо о заказе #%s отправлено: %s", order.pk, subject)


def send_order_payment_failed_email(order):
    """
    После неудачной попытки оплаты: заказ создан, оплата не прошла,
    оплатите в течение 6 часов или заказ будет отменён.
    """
    try:
        site_name = _order_email_context(order)["site_name"]
    except Exception:
        site_name = "Интернет-магазин"
    subject = f"{site_name} — заказ #{order.pk}: оплата не прошла"
    _send_order_email(
        order,
        subject,
        "orders/email/order_payment_failed.txt",
        "orders/email/order_payment_failed.html",
    )


def send_order_paid_email(order):
    """
    Заказ создан и успешно оплачен, ожидайте передачи в службу доставки.
    Вызывать один раз (флаг email_paid_sent).
    """
    try:
        site_name = _order_email_context(order)["site_name"]
    except Exception:
        site_name = "Интернет-магазин"
    subject = f"{site_name} — заказ #{order.pk} оплачен"
    _send_order_email(
        order,
        subject,
        "orders/email/order_paid.txt",
        "orders/email/order_paid.html",
    )


def send_order_in_delivery_email(order, tracking_number=None):
    """Заказ передан в доставку, с трек-номером СДЭК при наличии."""
    try:
        site_name = _order_email_context(order)["site_name"]
    except Exception:
        site_name = "Интернет-магазин"
    subject = f"{site_name} — заказ #{order.pk} передан в доставку"
    _send_order_email(
        order,
        subject,
        "orders/email/order_in_delivery.txt",
        "orders/email/order_in_delivery.html",
        context_extra={"tracking_number": tracking_number},
    )
