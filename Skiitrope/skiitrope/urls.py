from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("cart/", include("cart.urls")),
    path("", include("orders.urls")),
    path("", include("store.urls")),
]

# Serve uploaded media directly — also required in production, until product
# images move to object storage.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
