"""
Модели для управления пользователями и активацией аккаунтов.
"""
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    """
    Профиль пользователя (расширение стандартной модели User).
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="Пользователь",
    )
    phone = models.CharField(
        "Телефон",
        max_length=20,
        blank=True,
        help_text="Номер телефона для связи",
    )
    birth_date = models.DateField(
        "Дата рождения",
        null=True,
        blank=True,
    )
    address = models.TextField(
        "Адрес доставки",
        blank=True,
        help_text="Адрес для доставки заказов",
    )
    created_at = models.DateTimeField(
        "Дата создания",
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        "Дата обновления",
        auto_now=True,
    )

    class Meta:
        verbose_name = "профиль пользователя"
        verbose_name_plural = "профили пользователей"

    def __str__(self):
        return f"Профиль {self.user.username}"


class EmailVerification(models.Model):
    """
    Токены для подтверждения email при регистрации.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="email_verifications",
        verbose_name="Пользователь",
    )
    token = models.UUIDField(
        "Токен",
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )
    created_at = models.DateTimeField(
        "Дата создания",
        auto_now_add=True,
    )
    is_used = models.BooleanField(
        "Использован",
        default=False,
    )

    class Meta:
        verbose_name = "подтверждение email"
        verbose_name_plural = "подтверждения email"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Подтверждение для {self.user.email}"

    def is_expired(self):
        """Проверяет, истёк ли срок действия токена."""
        timeout = getattr(settings, "ACCOUNT_ACTIVATION_TIMEOUT", 86400)
        expiration_time = self.created_at + timedelta(seconds=timeout)
        return timezone.now() > expiration_time

    def is_valid(self):
        """Проверяет, действителен ли токен."""
        return not self.is_used and not self.is_expired()
