from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Product, ProductImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "order")
    list_editable = ("order",)
    list_filter = ("parent",)
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "is_primary", "order")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "price_display",
        "discount_display",
        "is_active",
        "created_at",
    )
    list_filter = ("category", "is_active")
    search_fields = ("name", "description")
    list_editable = ("is_active",)
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [ProductImageInline]
    fieldsets = (
        (None, {
            "fields": ("id", "category", "name", "price", "discount_percent")
        }),
        ("Описание", {"fields": ("description",)}),
        (
            "Габариты и вес",
            {
                "fields": ("length_mm", "width_mm", "height_mm", "weight_g"),
            },
        ),
        ("Публикация", {"fields": ("is_active", "created_at", "updated_at")}),
    )

    def price_display(self, obj):
        if obj.has_discount:
            return format_html(
                "<s>{}</s> {} ₽",
                obj.price,
                obj.discounted_price,
            )
        return f"{obj.price} ₽"

    price_display.short_description = "Цена"

    def discount_display(self, obj):
        if obj.has_discount:
            return f"-{obj.discount_percent}%"
        return "—"

    discount_display.short_description = "Скидка"
