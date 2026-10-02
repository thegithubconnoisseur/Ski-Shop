from django.db import transaction

from .emails import send_order_notification
from .models import Order, OrderItem


@transaction.atomic
def create_order_from_cart(cart, form, user=None):
    order = form.save(commit=False)
    order.user = user if (user and user.is_authenticated) else None
    order.subtotal = cart.subtotal
    order.shipping = cart.shipping
    order.total = cart.total
    order.currency = "USD"
    order.save()

    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                product=item["product"],
                product_name=item["product"].name,
                unit_price=item["price"],
                quantity=item["quantity"],
            )
            for item in cart
        ]
    )
    send_order_notification(order)
    return order
