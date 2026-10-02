from decimal import Decimal

from django.conf import settings

from store.models import Product

CART_SESSION_KEY = "cart"


class Cart:
    """A shopping cart stored in the user's session.

    Session layout: {"<product_id>": {"quantity": 3}, ...}
    Product objects are never stored in the session (not JSON serializable);
    they are looked up lazily while iterating.
    """

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(CART_SESSION_KEY)
        if not isinstance(cart, dict):
            cart = {}
        self.cart = cart

    def add(self, product, quantity=1, override=False):
        key = str(product.id)
        if key not in self.cart:
            self.cart[key] = {"quantity": 0}
        if override:
            self.cart[key]["quantity"] = quantity
        else:
            self.cart[key]["quantity"] += quantity
        if product.stock:
            self.cart[key]["quantity"] = min(self.cart[key]["quantity"], product.stock)
        self.cart[key]["quantity"] = max(self.cart[key]["quantity"], 1)
        self.save()

    def remove(self, product):
        key = str(product.id)
        if key in self.cart:
            del self.cart[key]
            self.save()

    def clear(self):
        self.session[CART_SESSION_KEY] = {}
        self.cart = self.session[CART_SESSION_KEY]
        self.save()

    def save(self):
        self.session[CART_SESSION_KEY] = self.cart
        self.session.modified = True

    def __iter__(self):
        products = {
            str(p.id): p
            for p in Product.objects.filter(
                id__in=self.cart.keys(), is_active=True
            ).select_related("category")
        }
        stale = [key for key in self.cart if key not in products]
        if stale:
            for key in stale:
                del self.cart[key]
            self.save()
        for key, item in self.cart.items():
            product = products[key]
            quantity = item["quantity"]
            yield {
                "product": product,
                "quantity": quantity,
                "price": product.price,
                "total": product.price * quantity,
            }

    def __len__(self):
        return len(self.cart)

    def __bool__(self):
        return len(self.cart) > 0

    @property
    def count(self):
        return sum(item["quantity"] for item in self.cart.values())

    @property
    def subtotal(self):
        return sum((item["total"] for item in self), Decimal("0.00"))

    @property
    def shipping(self):
        if not self.cart:
            return Decimal("0.00")
        if self.subtotal >= Decimal(settings.FREE_SHIPPING_THRESHOLD):
            return Decimal("0.00")
        return Decimal(settings.FLAT_SHIPPING_RATE)

    @property
    def free_shipping_remaining(self):
        threshold = Decimal(settings.FREE_SHIPPING_THRESHOLD)
        if not self.cart or self.subtotal >= threshold:
            return Decimal("0.00")
        return threshold - self.subtotal

    @property
    def total(self):
        return self.subtotal + self.shipping
