from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.static import serve as serve_static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("api/", include("api.urls")),
    path("cart/", include("cart.urls")),
    path("", include("orders.urls")),
    path("", include("store.urls")),
    # Media must be routed explicitly: the classic static() helper
    # no-ops when DEBUG=False, which 404s every product image in production.
    path(
        settings.MEDIA_URL.lstrip("/") + "<path:path>",
        serve_static,
        {"document_root": settings.MEDIA_ROOT},
    ),
]
