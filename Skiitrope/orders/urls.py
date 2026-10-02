from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/success/", views.checkout_success, name="checkout_success"),
    path("checkout/cancelled/", views.checkout_cancelled, name="checkout_cancelled"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
]
