"""
Ограничение частоты запросов (rate limiting) для входа и других действий.

Используется кэш Django.
Ключ: login_attempts_{ip}, значение: число попыток, таймаут 15 минут.
После 10 неудачных попыток входа с одного IP возвращается 429.
"""
from django.core.cache import cache
from django.http import HttpResponse

LOGIN_RATE_LIMIT_KEY_PREFIX = "login_attempts_"
LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 10
LOGIN_RATE_LIMIT_TIMEOUT = 900  # 15 минут


def get_client_ip(request):
    """IP клиента с учётом X-Forwarded-For за прокси."""
    xff = (request.META.get("HTTP_X_FORWARDED_FOR") or "").strip()
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def get_login_attempts_cache_key(request):
    return f"{LOGIN_RATE_LIMIT_KEY_PREFIX}{get_client_ip(request)}"


def check_login_rate_limit(request):
    """
    Проверяет, не превышен ли лимит попыток входа.
    Возвращает None, если можно продолжать, иначе HttpResponse с 429.
    """
    if request.method != "POST":
        return None
    key = get_login_attempts_cache_key(request)
    attempts = cache.get(key, 0)
    if attempts >= LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
        return HttpResponse(
            "Слишком много неудачных попыток входа. "
            "Попробуйте через 15 минут.",
            status=429,
            content_type="text/plain; charset=utf-8",
        )
    return None


def increment_login_attempts(request):
    """Увеличивает счётчик неудачных попыток входа для IP."""
    key = get_login_attempts_cache_key(request)
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, LOGIN_RATE_LIMIT_TIMEOUT)


def clear_login_attempts(request):
    """Сбрасывает счётчик после успешного входа."""
    key = get_login_attempts_cache_key(request)
    cache.delete(key)
