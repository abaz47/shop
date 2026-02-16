from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("<uuid:pk>/", views.product_detail, name="product_detail"),
    path("<slug:slug>/", views.product_list, name="product_list_by_category"),
]
