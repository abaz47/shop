"""
Регистрация моделей core в админке.
"""
from django.contrib import admin

from .models import LegalPage, SiteSettings


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

    def content_preview(self, obj):
        if not obj.content:
            return "—"
        text = obj.content.strip()[:80].replace("\n", " ")
        return f"{text}…" if len(obj.content) > 80 else text

    content_preview.short_description = "Фрагмент содержимого"
