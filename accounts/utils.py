"""
Утилиты для работы с email и асинхронной отправкой писем.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import local

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)

# Thread-local storage для хранения executor в каждом потоке
_thread_local = local()


def get_email_executor():
    """
    Возвращает ThreadPoolExecutor для асинхронной отправки писем.
    Использует thread-local storage для переиспользования executor.
    """
    if not hasattr(_thread_local, "executor"):
        _thread_local.executor = ThreadPoolExecutor(max_workers=2)
    return _thread_local.executor


def send_email_async(
    subject,
    message,
    from_email,
    recipient_list,
    html_message=None
):
    """
    Асинхронно отправляет email через ThreadPoolExecutor.

    Args:
        subject: Тема письма
        message: Текст письма (обязательно)
        from_email: Отправитель (None = DEFAULT_FROM_EMAIL)
        recipient_list: Список получателей
        html_message: HTML версия письма (опционально)
    """
    executor = get_email_executor()

    def _send():
        try:
            email = EmailMultiAlternatives(
                subject=subject,
                body=message,
                from_email=from_email or settings.DEFAULT_FROM_EMAIL,
                to=recipient_list,
            )
            
            # Добавляем HTML версию, если она есть
            if html_message:
                email.attach_alternative(html_message, "text/html")
            
            email.send(fail_silently=False)
            logger.info(f"Email отправлен: {subject} -> {recipient_list}")
        except Exception as e:
            logger.error(f"Ошибка отправки email: {e}", exc_info=True)

    executor.submit(_send)


def send_activation_email(user, verification_token):
    """
    Отправляет письмо с ссылкой активации аккаунта.

    Args:
        user: Объект User
        verification_token: UUID токен из EmailVerification
    """
    # Домен и название — из Django Sites
    try:
        from django.contrib.sites.models import Site
        current_site = Site.objects.get_current()
        site_domain = current_site.domain
        site_name = current_site.name or "Интернет-магазин"
    except Exception:
        site_domain = (
            getattr(settings, "ALLOWED_HOSTS", ["localhost"]) or ["localhost"]
        )[0]
        if site_domain == "*":
            site_domain = "localhost"
        site_name = "Интернет-магазин"

    # Определяем протокол (https в продакшене, http локально)
    protocol = "https" if not settings.DEBUG else "http"
    activation_url = (
        f"{protocol}://{site_domain}"
        + reverse(
            "accounts:activate", kwargs={"token": str(verification_token)}
        )
    )

    subject = "Подтверждение регистрации"
    context = {
        "user": user,
        "activation_url": activation_url,
        "site_name": site_name,
    }

    # Текстовая версия
    message = render_to_string("accounts/email/activation_email.txt", context)

    # HTML версия
    html_message = render_to_string(
        "accounts/email/activation_email.html",
        context
    )

    send_email_async(
        subject=subject,
        message=message,
        from_email=None,  # Используется DEFAULT_FROM_EMAIL
        recipient_list=[user.email],
        html_message=html_message,
    )
