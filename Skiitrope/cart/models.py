from django.conf import settings
from django.db import models

from store.models import Product


class CartItem(models.Model):
    """A product line in a signed-in user's cart.

    Anonymous visitors keep their cart in the session; at login the session
    cart is merged into these rows, which are what both the website and the
    mobile app read and write — that shared table is the cart sync.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="cart_items"
    )
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"], name="unique_user_product_cart_item"
            ),
        ]

    def __str__(self):
        return f"{self.quantity} × {self.product.name} ({self.user.email})"
