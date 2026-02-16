"""
Регистрация моделей core в админке.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import LegalPage, SiteImage, SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("site_name", "site_description")
    fields = ("site_name", "site_description")

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not change:
            obj.key = "main"
        super().save_model(request, obj, form, change)


@admin.register(LegalPage)
class LegalPageAdmin(admin.ModelAdmin):
    list_display = ("slug", "title", "content_preview")
    list_filter = ("slug",)
    search_fields = ("title", "content")
    prepopulated_fields = {}
    fields = ("slug", "title", "content")

    def content_preview(self, obj):
        if not obj.content:
            return "—"
        text = obj.content.strip()[:80].replace("\n", " ")
        return f"{text}…" if len(obj.content) > 80 else text

    content_preview.short_description = "Фрагмент содержимого"


@admin.register(SiteImage)
class SiteImageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "image_preview",
        "slug",
        "url_display",
        "created_at"
    )
    list_filter = ("category", "created_at")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "url_display", "html_code_display")
    fieldsets = (
        (None, {
            "fields": ("name", "slug", "category", "image")
        }),
        ("Дополнительно", {
            "fields": ("description", "created_at")
        }),
        ("Использование", {
            "fields": ("url_display", "html_code_display"),
            "classes": ("collapse",),
        }),
    )

    def image_preview(self, obj):
        """Превью изображения в списке."""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 100px;" />',
                obj.image.url
            )
        return "—"

    image_preview.short_description = "Превью"

    def url_display(self, obj):
        """Отображение URL изображения."""
        if obj.image:
            url = obj.get_url()
            return format_html('<code>{}</code>', url)
        return "—"

    url_display.short_description = "URL изображения"

    def html_code_display(self, obj):
        """Примеры кода для вставки."""
        if obj.image:
            url = obj.get_url()
            alt = obj.name
            slug = obj.slug

            examples = [
                f'<img src="{url}" alt="{alt}" />',
                '{% load site_images %}',
                f'{{% site_image "{slug}" alt="{alt}" '
                f'css_class="payment-logo" %}}',
                f'{{% get_site_image "{slug}" as img %}}'
                f'{{{{ img.get_url }}}}',
            ]

            html_content = '<br>'.join([
                format_html(
                    '<code style="display: block; '
                    'padding: 5px; margin: 5px 0; '
                    'background: #f5f5f5; border-radius: 3px;">{}</code>',
                    example
                ) for example in examples
            ])

            return format_html(
                '<div style="margin-top: 10px;">'
                '<strong>Прямой HTML:</strong><br>{}</div>',
                html_content
            )
        return "—"

    html_code_display.short_description = "Примеры кода"
