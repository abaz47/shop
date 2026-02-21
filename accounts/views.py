"""
Представления для регистрации, активации
и управления профилем.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView,
    LogoutView,
    PasswordResetView as DjangoPasswordResetView,
)
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView

from .forms import (
    CustomPasswordResetForm,
    LoginForm,
    ProfileEditForm,
    RegistrationForm,
)
from .models import EmailVerification, UserProfile
from .utils import send_activation_email, send_email_async


class RegisterView(CreateView):
    """
    Представление для регистрации нового пользователя.
    """

    form_class = RegistrationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("accounts:register_success")

    def form_valid(self, form):
        """
        Создаёт пользователя и отправляет письмо активации.
        """
        user = form.save()
        # Создаём токен активации
        verification = EmailVerification.objects.create(user=user)
        # Отправляем письмо асинхронно
        send_activation_email(user, verification.token)
        return super().form_valid(form)


def register_success(request):
    """Страница успешной регистрации."""
    return render(request, "accounts/register_success.html")


def activate_account(request, token):
    """
    Активирует аккаунт пользователя по токену из email.
    """
    try:
        verification = EmailVerification.objects.get(
            token=token,
            is_used=False,
        )
    except EmailVerification.DoesNotExist:
        messages.error(
            request,
            "Неверная или уже использованная "
            "ссылка активации.",
        )
        return redirect("accounts:login")

    if verification.is_expired():
        messages.error(
            request,
            "Срок действия ссылки активации истёк. "
            "Пожалуйста, зарегистрируйтесь заново.",
        )
        return redirect("accounts:register")

    if not verification.is_valid():
        messages.error(
            request,
            "Ссылка активации недействительна.",
        )
        return redirect("accounts:login")

    # Активируем аккаунт
    user = verification.user
    user.is_active = True
    user.save()

    # Помечаем токен как использованный
    verification.is_used = True
    verification.save()

    return redirect("accounts:login")


class CustomLoginView(LoginView):
    """
    Представление для входа пользователя.
    """

    form_class = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        """
        Проверяет, что аккаунт активирован перед входом.
        После входа переносит корзину из сессии в корзину пользователя.
        """
        user = form.get_user()
        if not user.is_active:
            messages.error(
                self.request,
                "Ваш аккаунт не активирован. "
                "Проверьте почту для подтверждения.",
            )
            return redirect("accounts:login")

        session_key_before = self.request.session.session_key
        response = super().form_valid(form)

        # Перенос корзины анонима в корзину пользователя
        if session_key_before:
            from cart.models import Cart
            from cart.utils import get_or_create_cart, merge_carts

            session_cart = Cart.objects.filter(
                session_key=session_key_before,
                user__isnull=True,
            ).first()
            if session_cart:
                user_cart = get_or_create_cart(self.request)
                merge_carts(session_cart, user_cart)

        return response


class CustomLogoutView(LogoutView):
    """
    Представление для выхода пользователя.
    """

    next_page = reverse_lazy("catalog:product_list")

    pass


@login_required
def profile_view(request):
    """Отображение профиля пользователя."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, "accounts/profile.html", {"profile": profile})


class ProfileEditView(UpdateView):
    """
    Представление для редактирования
    профиля пользователя.
    """

    model = UserProfile
    form_class = ProfileEditForm
    template_name = "accounts/profile_edit.html"
    success_url = reverse_lazy("accounts:profile")

    def get_object(self, queryset=None):
        """
        Возвращает профиль текущего пользователя.
        """
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    def get_form_kwargs(self):
        """Передаёт пользователя в форму."""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        """
        Сохраняет изменения и показывает сообщение.
        """
        messages.success(
            self.request,
            "Профиль успешно обновлён."
        )
        return super().form_valid(form)


class PasswordResetView(DjangoPasswordResetView):
    """
    Кастомное представление для восстановления пароля
    с добавлением site_name и HTML-версии письма.
    """

    form_class = CustomPasswordResetForm
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/email/password_reset_email.html"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")

    def get_context_data(self, **kwargs):
        """
        Добавляет site_name в контекст из Django Sites.
        """
        context = super().get_context_data(**kwargs)
        try:
            from django.contrib.sites.shortcuts import get_current_site
            current_site = get_current_site(self.request)
            context["site_name"] = (
                current_site.name or "Интернет-магазин"
            )
        except Exception:
            context["site_name"] = "Интернет-магазин"
        return context

    def get_extra_email_context(self):
        """
        Добавляет site_name в контекст email-шаблона
        из Django Sites.
        """
        try:
            context = super().get_extra_email_context()
        except AttributeError:
            # Если базовый класс не имеет этого метода,
            # создаём пустой словарь
            context = {}

        if not context:
            context = {}

        try:
            from django.contrib.sites.models import Site
            context["site_name"] = (
                Site.objects.get_current().name or "Интернет-магазин"
            )
        except Exception:
            context["site_name"] = "Интернет-магазин"
        return context

    def form_valid(self, form):
        """
        Переопределяем отправку письма
        для использования HTML-версии.
        """
        from django.conf import settings
        from django.template.loader import render_to_string

        # Получаем email из формы
        email = form.cleaned_data["email"]

        # Находим пользователей с таким email
        # (используем метод экземпляра формы)
        active_users = form.get_users(email)

        if not active_users:
            # Если пользователей нет, просто редиректим
            return super().form_valid(form)

        # Создаём базовый контекст для письма
        context = {}
        try:
            from django.contrib.sites.models import Site
            context["site_name"] = (
                Site.objects.get_current().name or "Интернет-магазин"
            )
        except Exception:
            context["site_name"] = "Интернет-магазин"

        # Для каждого пользователя отправляем письмо
        for user in active_users:
            # Генерируем токены для восстановления пароля
            from django.contrib.auth.tokens import (
                default_token_generator,
            )
            from django.utils.encoding import force_bytes
            from django.utils.http import urlsafe_base64_encode

            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            # Добавляем данные в контекст
            protocol = "https" if not settings.DEBUG else "http"
            context.update({
                "user": user,
                "uid": uid,
                "token": token,
                "protocol": protocol,
            })

            # Получаем домен из Django Sites
            try:
                from django.contrib.sites.models import Site
                current_site = Site.objects.get_current()
                context["domain"] = current_site.domain
            except Exception:
                allowed_hosts = (
                    getattr(settings, "ALLOWED_HOSTS", ["localhost"])
                    or ["localhost"]
                )
                context["domain"] = allowed_hosts[0]
                if context["domain"] == "*":
                    context["domain"] = "localhost"

            # Рендерим тему письма
            subject = render_to_string(
                self.subject_template_name,
                context,
            ).strip()

            # Рендерим HTML-версию письма
            html_message = render_to_string(
                self.email_template_name,
                context,
            )

            # Рендерим текстовую версию из шаблона
            text_template = (
                "accounts/email/password_reset_email.txt"
            )
            message = render_to_string(text_template, context)

            # Отправляем письмо асинхронно
            send_email_async(
                subject=subject,
                message=message,
                from_email=None,  # Используется DEFAULT_FROM_EMAIL
                recipient_list=[user.email],
                html_message=html_message,
            )

        return HttpResponseRedirect(self.get_success_url())
