from django.urls import path

from . import views

app_name = "tbank"

urlpatterns = [
    path(
        "start/<int:order_id>/",
        views.start_payment_view,
        name="start",
    ),
    path(
        "success/<int:order_id>/",
        views.payment_success_view,
        name="success",
    ),
    path(
        "fail/<int:order_id>/",
        views.payment_fail_view,
        name="fail",
    ),
    path(
        "notification/",
        views.notification_view,
        name="notification",
    ),
]
