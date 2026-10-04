from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers

from orders.models import Order, OrderItem
from store.models import Category, Product

User = get_user_model()


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class ProductListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    image = serializers.SerializerMethodField()
    in_stock = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "price",
            "image",
            "stock",
            "in_stock",
            "is_featured",
            "category",
        ]

    def get_image(self, product):
        if not product.image:
            return None
        return self.context["request"].build_absolute_uri(product.image.url)


class ProductDetailSerializer(ProductListSerializer):
    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + ["description"]


class OrderItemSerializer(serializers.ModelSerializer):
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ["product_name", "unit_price", "quantity", "line_total"]

    def get_line_total(self, item):
        return str(item.line_total)


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "number",
            "status",
            "email",
            "subtotal",
            "shipping",
            "total",
            "currency",
            "created_at",
            "items",
        ]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["email", "first_name", "last_name"]


def cart_payload(cart, request):
    """JSON shape shared by every /api/cart/ response, so the app always
    receives the full current cart state after each change."""
    items = [
        {
            "product": ProductListSerializer(
                item["product"], context={"request": request}
            ).data,
            "quantity": item["quantity"],
            "price": str(item["price"]),
            "total": str(item["total"]),
        }
        for item in cart
    ]
    return {
        "items": items,
        "count": cart.count,
        "subtotal": str(cart.subtotal),
        "shipping": str(cart.shipping),
        "free_shipping_remaining": str(cart.free_shipping_remaining),
        "total": str(cart.total),
        "currency": settings.SHOP_CURRENCY,
        "currency_symbol": settings.SHOP_CURRENCY_SYMBOL,
    }
