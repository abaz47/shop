"""
Тесты для регистрации пользователей и профиля.
"""
import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from accounts.forms import RegistrationForm
from accounts.models import UserProfile
from accounts.phone import normalize_russian_phone


def test_registration_phone_saved_to_profile(client, db):
    """
    При регистрации указанный телефон сохраняется в профиль пользователя.
    """
    User = get_user_model()
    assert User.objects.count() == 0
    assert UserProfile.objects.count() == 0

    data = {
        "email": "user@example.com",
        "phone": "+7 999 123-45-67",
        "first_name": "Иван",
        "last_name": "Иванов",
        "password1": "StrongPass123!",
        "password2": "StrongPass123!",
    }

    form = RegistrationForm(data=data)
    assert form.is_valid(), form.errors

    user = form.save()
    assert user.username == "user@example.com"
    profile = UserProfile.objects.get(user=user)
    assert profile.phone == "+79991234567"


def test_normalize_russian_phone_variants():
    assert normalize_russian_phone("+7 (912) 345-67-89") == "+79123456789"
    assert normalize_russian_phone("89123456789") == "+79123456789"
    assert normalize_russian_phone("9123456789") == "+79123456789"


def test_normalize_russian_phone_invalid():
    with pytest.raises(ValidationError):
        normalize_russian_phone("123")
    with pytest.raises(ValidationError):
        normalize_russian_phone("+1 234 567 8901")


def test_registration_rejects_invalid_phone():
    data = {
        "email": "x@example.com",
        "phone": "+7 12",
        "password1": "StrongPass123!",
        "password2": "StrongPass123!",
    }
    form = RegistrationForm(data=data)
    assert not form.is_valid()
    assert "phone" in form.errors
