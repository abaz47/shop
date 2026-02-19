"""
URL-маршруты для приложения accounts.
"""
from django.contrib.auth.views import (
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView,
)
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.RegisterView.as_view(), name="register"),
    path("register/success/", views.register_success, name="register_success"),
    path("activate/<uuid:token>/", views.activate_account, name="activate"),
    path("login/", views.CustomLoginView.as_view(), name="login"),
    path("logout/", views.CustomLogoutView.as_view(), name="logout"),
    path("profile/", views.profile_view, name="profile"),
    path(
        "profile/edit/",
        views.ProfileEditView.as_view(),
        name="profile_edit"
    ),
    # Восстановление пароля
    path(
        "password-reset/",
        views.PasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        PasswordResetDoneView.as_view(
            template_name="accounts/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset-confirm/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url="/accounts/password-reset-complete/",
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset-complete/",
        PasswordResetCompleteView.as_view(
            template_name="accounts/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),
]
