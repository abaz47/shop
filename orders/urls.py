"""
URL-маршруты приложения orders.
"""
from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.order_list, name="list"),
    path("checkout/", views.checkout_view, name="checkout"),
    path("checkout/cities/", views.checkout_cities, name="checkout_cities"),
    path("checkout/tariffs/", views.checkout_tariffs, name="checkout_tariffs"),
    path(
        "checkout/success/<int:order_id>/",
        views.checkout_success,
        name="success",
    ),
]
