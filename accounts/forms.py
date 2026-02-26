"""
Формы для регистрации и редактирования профиля.
"""
from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    UserCreationForm,
)
from django.core.exceptions import ValidationError
from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV3

from .models import UserProfile


class RegistrationForm(UserCreationForm):
    """
    Форма регистрации нового пользователя с reCAPTCHA.
    """

    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
        help_text="На этот адрес придёт письмо для подтверждения регистрации",
    )
    first_name = forms.CharField(
        label="Имя",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_name = forms.CharField(
        label="Фамилия",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    # reCAPTCHA (только если ключи заданы в .env)
    recaptcha = ReCaptchaField(
        widget=ReCaptchaV3(),
        required=False,  # Не обязательна, если ключи не заданы
    )

    class Meta:
        model = UserCreationForm.Meta.model
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Приводим все поля к единому Bootstrap-стилю
        for name in ("username", "password1", "password2"):
            if name in self.fields:
                css_classes = self.fields[name].widget.attrs.get("class", "")
                css_classes = f"{css_classes} form-control".strip()
                self.fields[name].widget.attrs["class"] = css_classes

        # Делаем reCAPTCHA обязательной только если ключи заданы
        from django.conf import settings
        recaptcha_public = getattr(settings, "RECAPTCHA_PUBLIC_KEY", "")
        recaptcha_private = getattr(settings, "RECAPTCHA_PRIVATE_KEY", "")
        if not (recaptcha_public and recaptcha_private):
            # Удаляем поле reCAPTCHA, если ключи не заданы
            self.fields.pop("recaptcha", None)
        else:
            self.fields["recaptcha"].required = True

    def clean_email(self):
        """Проверяет уникальность email."""
        email = self.cleaned_data.get("email")
        if email and self.Meta.model.objects.filter(email=email).exists():
            raise ValidationError(
                "Пользователь с таким email уже зарегистрирован."
            )
        return email

    def save(self, commit=True):
        """Сохраняет пользователя с неактивным аккаунтом."""
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        user.is_active = False  # Аккаунт неактивен до подтверждения email
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """
    Форма входа с Bootstrap стилями и reCAPTCHA.
    """

    username = forms.CharField(
        label="Имя пользователя или Email",
        widget=forms.TextInput(
            attrs={"class": "form-control", "autofocus": True}
        ),
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )

    # reCAPTCHA (только если ключи заданы в .env)
    recaptcha = ReCaptchaField(
        widget=ReCaptchaV3(),
        required=False,  # Не обязательна, если ключи не заданы
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем reCAPTCHA обязательной только если ключи заданы
        from django.conf import settings
        recaptcha_public = getattr(settings, "RECAPTCHA_PUBLIC_KEY", "")
        recaptcha_private = getattr(settings, "RECAPTCHA_PRIVATE_KEY", "")
        if not (recaptcha_public and recaptcha_private):
            # Удаляем поле reCAPTCHA, если ключи не заданы
            self.fields.pop("recaptcha", None)
        else:
            self.fields["recaptcha"].required = True


class CustomPasswordResetForm(PasswordResetForm):
    """
    Форма восстановления пароля с Bootstrap стилями.
    """

    email = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(
            attrs={"class": "form-control", "autocomplete": "email"}
        ),
    )


class ProfileEditForm(forms.ModelForm):
    """
    Форма редактирования профиля: Фамилия, Имя, Отчество, Телефон и др.
    Email и логин в форме не меняются (только отображаются в ЛК).
    """

    first_name = forms.CharField(
        label="Имя",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_name = forms.CharField(
        label="Фамилия",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = UserProfile
        fields = ("patronymic", "phone")
        widgets = {
            "patronymic": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name

    def save(self, commit=True):
        """Сохраняет изменения в профиле и пользователе (без смены email)."""
        profile = super().save(commit=False)
        self.user.first_name = self.cleaned_data.get("first_name", "")
        self.user.last_name = self.cleaned_data.get("last_name", "")
        if commit:
            self.user.save()
            profile.save()
        return profile
