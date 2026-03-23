"""
Нормализация и проверка российских телефонных номеров.
"""
import re

from django.core.exceptions import ValidationError

RU_PHONE_ERROR = (
    "Введите российский номер: 10 цифр после +7. "
    "Допускается ввод с 8 вместо +7."
)


def normalize_russian_phone(value):
    """
    Проверяет российский номер и приводит к виду +7XXXXXXXXXX.

    Ожидается 10 цифр национальной части (после кода страны 7):
    мобильный (9xx…) или городской (3xx / 4xx / 8xx и т.д.).
    """
    if value is None:
        value = ""
    digits = re.sub(r"\D", "", str(value).strip())
    if not digits:
        raise ValidationError(RU_PHONE_ERROR)

    if digits[0] == "8" and len(digits) == 11:
        digits = "7" + digits[1:]

    if digits.startswith("7") and len(digits) == 11:
        national = digits[1:]
    elif len(digits) == 10:
        national = digits
    else:
        raise ValidationError(RU_PHONE_ERROR)

    if len(national) != 10 or not re.match(r"^[3489]\d{9}$", national):
        raise ValidationError(RU_PHONE_ERROR)

    return "+7" + national
