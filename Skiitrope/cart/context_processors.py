from django.conf import settings

from .cart import get_cart


def cart(request):
    return {
        "cart": get_cart(request),
        "shop": {
            "currency": settings.SHOP_CURRENCY,
            "currency_symbol": settings.SHOP_CURRENCY_SYMBOL,
            "free_shipping_threshold": settings.FREE_SHIPPING_THRESHOLD,
            "flat_shipping_rate": settings.FLAT_SHIPPING_RATE,
        },
    }
