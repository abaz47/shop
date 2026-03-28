"""
Нормализация и проверка телефонных номеров.
"""
import re

import phonenumbers
from django.core.exceptions import ValidationError
from phonenumbers import NumberParseException, PhoneNumberFormat

# Регионы libphonenumber для стран бывшего СССР (для регистрации в магазине).
# +7 покрывает RU и KZ; остальные — отдельные коды стран.
CIS_REGION_CODES = frozenset(
    {"RU", "KZ", "BY", "UA", "AM", "AZ", "GE", "KG", "MD", "TJ", "TM", "UZ"}
)

PHONE_ERROR = (
    "Укажите номер в международном формате с кодом страны: "
    "«+» и далее цифры (например +7 912 345-67-89, +375 29 123-45-67)."
)

PHONE_ERROR_REGION = (
    "Допускаются номера стран СНГ и ближнего зарубежья."
)


def _digits_only(value):
    return re.sub(r"\D", "", str(value).strip())


def _prepare_e164_candidate(raw):
    """
    Строит строку для parse():
    «+» и полный номер, либо только цифры полного международного номера.
    """
    raw = str(raw).strip()
    if not raw:
        return None

    if raw.startswith("+"):
        return raw

    digits = _digits_only(raw)
    if not digits:
        return None

    return "+" + digits


def normalize_cis_phone(value):
    """
    Проверяет номер (страны СНГ по списку CIS_REGION_CODES) и возвращает E.164.

    Ожидается международный номер с кодом страны
    (ввод с «+» или те же цифры без «+»).
    """
    if value is None:
        value = ""
    raw = str(value).strip()
    if not raw:
        raise ValidationError(PHONE_ERROR)

    to_parse = _prepare_e164_candidate(raw)
    if not to_parse:
        raise ValidationError(PHONE_ERROR)

    try:
        num = phonenumbers.parse(to_parse, None)
    except NumberParseException:
        raise ValidationError(PHONE_ERROR) from None

    if not phonenumbers.is_valid_number(num):
        raise ValidationError(PHONE_ERROR)

    region = phonenumbers.region_code_for_number(num)
    if region not in CIS_REGION_CODES:
        raise ValidationError(PHONE_ERROR_REGION)

    return phonenumbers.format_number(num, PhoneNumberFormat.E164)
