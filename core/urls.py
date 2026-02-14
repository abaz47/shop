from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("<slug:slug>/", views.legal_page, name="legal_page"),
]
