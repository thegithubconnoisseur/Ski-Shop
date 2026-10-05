from django.urls import path

from . import views

app_name = "api"

urlpatterns = [
    path("products/", views.product_list, name="product_list"),
    path("products/<slug:slug>/", views.product_detail, name="product_detail"),
    path("categories/", views.category_list, name="category_list"),
    path("cart/", views.cart_detail, name="cart_detail"),
    path("cart/add/", views.cart_add, name="cart_add"),
    path("cart/update/", views.cart_update, name="cart_update"),
    path("cart/remove/", views.cart_remove, name="cart_remove"),
    path("auth/google/", views.google_auth, name="google_auth"),
    path("auth/login/", views.email_login, name="email_login"),
    path("auth/logout/", views.logout, name="logout"),
    path("auth/mobile/finish/", views.mobile_auth_finish, name="mobile_auth_finish"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/", views.order_list, name="order_list"),
]
