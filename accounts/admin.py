"""
Админ-панель для моделей accounts.
"""
from django.contrib import admin

from .models import EmailVerification, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Админка для профилей пользователей."""

    list_display = ("user", "phone", "created_at")
    search_fields = ("user__username", "user__email", "phone")
    readonly_fields = ("created_at", "updated_at")


@admin.register(EmailVerification)
class EmailVerificationAdmin(admin.ModelAdmin):
    """Админка для подтверждений email."""

    list_display = ("user", "token", "created_at", "is_used", "is_expired")
    list_filter = ("is_used", "created_at")
    search_fields = ("user__username", "user__email", "token")
    readonly_fields = ("token", "created_at")

    def is_expired(self, obj):
        """Отображает, истёк ли токен."""
        return obj.is_expired()

    is_expired.boolean = True
    is_expired.short_description = "Истёк"
