"""
Тесты для регистрации пользователей и профиля.
"""
from django.contrib.auth import get_user_model

from accounts.forms import RegistrationForm
from accounts.models import UserProfile


def test_registration_phone_saved_to_profile(client, db):
    """
    При регистрации указанный телефон сохраняется в профиль пользователя.
    """
    User = get_user_model()
    assert User.objects.count() == 0
    assert UserProfile.objects.count() == 0

    data = {
        "username": "newuser",
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
    profile = UserProfile.objects.get(user=user)
    assert profile.phone == data["phone"]
