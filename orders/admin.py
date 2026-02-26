"""
Админка заказов.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "price", "quantity", "line_total_display")
    can_delete = True

    def line_total_display(self, obj):
        total = obj.line_total
        return f"{total:.2f} ₽" if total is not None else "—"

    line_total_display.short_description = "Сумма"


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
    readonly_fields = ("created_at", "updated_at")
    inlines = [OrderItemInline]
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
        ("Прочее", {"fields": ("comment", "created_at", "updated_at")}),
    )

    def total_display(self, obj):
        return format_html("{} ₽", obj.total)

    total_display.short_description = "Итого"
