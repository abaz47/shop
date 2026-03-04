"""
Админка заказов.
"""
import logging

from django.contrib import admin, messages
from django.utils.html import format_html

from tbank.client import TbankAPIError, TbankClient

from .models import Order, OrderItem

logger = logging.getLogger(__name__)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "price", "quantity", "line_total_display")
    can_delete = True

    def line_total_display(self, obj):
        total = obj.line_total
        return f"{total:.2f} ₽" if total is not None else "—"

    line_total_display.short_description = "Сумма"


def _cancel_orders_action(modeladmin, request, queryset):
    """
    Admin-action:
    отменяет платёж в T‑Банке и переводит заказ в статус «Возврат».
    Доступно только для заказов в статусе «Оплачен» с заполненным PaymentId.
    """

    ok_count = 0
    for order in queryset:
        if order.status != Order.Status.PAID:
            modeladmin.message_user(
                request,
                f"Заказ #{order.pk}: отмена доступна только для оплаченных "
                f"(заказов, текущий статус: {order.get_status_display()}).",
                level=messages.WARNING,
            )
            continue

        if not order.tbank_payment_id:
            modeladmin.message_user(
                request,
                f"Заказ #{order.pk}: PaymentId T‑Банка не сохранён — "
                "отмена через API невозможна.",
                level=messages.ERROR,
            )
            continue

        try:
            client = TbankClient()
            client.cancel_payment(payment_id=order.tbank_payment_id)
        except TbankAPIError as exc:
            logger.exception(
                "Admin cancel_payment failed for order=%s payment_id=%s",
                order.pk,
                order.tbank_payment_id,
            )
            modeladmin.message_user(
                request,
                f"Заказ #{order.pk}: ошибка при отмене в T‑Банке — {exc}.",
                level=messages.ERROR,
            )
            continue

        order.status = Order.Status.REFUNDED
        order.save(update_fields=["status", "updated_at"])
        ok_count += 1

    if ok_count:
        modeladmin.message_user(
            request,
            f"Успешно отменено {ok_count} заказ(ов).",
            level=messages.SUCCESS,
        )


_cancel_orders_action.short_description = "Отменить платёж в T‑Банке (Возврат)"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "user",
        "status",
        "delivery_method",
        "delivery_tariff_code",
        "total_display",
        "recipient_phone",
    )
    list_filter = ("status", "delivery_method", "delivery_type", "created_at")
    search_fields = (
        "recipient_name",
        "recipient_phone",
        "recipient_email",
        "id",
    )
    readonly_fields = ("created_at", "updated_at", "tbank_payment_id")
    inlines = [OrderItemInline]
    actions = [_cancel_orders_action]
    fieldsets = (
        (None, {
            "fields": ("user", "status", "delivery_method", "delivery_type")
        }),
        (
            "Суммы",
            {"fields": ("products_total", "delivery_cost", "total")},
        ),
        (
            "Получатель",
            {
                "fields": (
                    "recipient_name",
                    "recipient_phone",
                    "recipient_email",
                )
            },
        ),
        (
            "Доставка",
            {"fields": (
                "delivery_tariff_code",
                "city_code",
                "delivery_address",
                "pvz_code",
                "cdek_order_uuid",
            )},
        ),
        (
            "T‑Банк",
            {"fields": ("tbank_payment_id",)},
        ),
        ("Прочее", {"fields": ("comment", "created_at", "updated_at")}),
    )

    def total_display(self, obj):
        return format_html("{} ₽", obj.total)

    total_display.short_description = "Итого"
