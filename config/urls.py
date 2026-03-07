"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from core.sitemaps import ProductSitemap, StaticSitemap
from core import views as core_views

handler404 = "core.views.page_not_found"
handler500 = "core.views.server_error"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("robots.txt", core_views.robots_txt),
    path(
        "sitemap.xml",
        sitemap,
        {"sitemaps": {"static": StaticSitemap, "products": ProductSitemap}},
        name="django.contrib.sitemaps.views.sitemap",
    ),
    path("accounts/", include("accounts.urls")),
    path("cart/", include("cart.urls")),
    path("orders/", include("orders.urls")),
    path("tbank/", include("tbank.urls")),
    path("legal/", include("core.urls")),
    path("", include("catalog.urls")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
