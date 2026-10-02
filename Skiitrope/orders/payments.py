import logging

import stripe
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .emails import send_order_confirmation
from .models import Order

logger = logging.getLogger(__name__)


def stripe_configured():
    return bool(settings.STRIPE_SECRET_KEY)


def create_checkout_session(order, request):
    """Create a Stripe Checkout session for the order (charges in USD)."""
    line_items = [
        {
            "price_data": {
                "currency": "usd",
                "product_data": {"name": item.product_name},
                "unit_amount": int(item.unit_price * 100),
            },
            "quantity": item.quantity,
        }
        for item in order.items.all()
    ]
    if order.shipping > 0:
        line_items.append(
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": "Shipping"},
                    "unit_amount": int(order.shipping * 100),
                },
                "quantity": 1,
            }
        )

    success_url = request.build_absolute_uri(
        reverse("orders:checkout_success")
    ) + "?session_id={CHECKOUT_SESSION_ID}"

    return stripe.checkout.Session.create(
        api_key=settings.STRIPE_SECRET_KEY,
        mode="payment",
        line_items=line_items,
        customer_email=order.email,
        success_url=success_url,
        cancel_url=request.build_absolute_uri(reverse("orders:checkout_cancelled")),
        metadata={"order_number": order.number},
        payment_intent_data={"metadata": {"order_number": order.number}},
        locale="auto",
    )


def retrieve_checkout_session(session_id):
    return stripe.checkout.Session.retrieve(
        session_id, api_key=settings.STRIPE_SECRET_KEY
    )


def mark_order_paid(order, payment_intent_id=""):
    """Idempotently flag an order as paid and send the confirmation email."""
    if order.status == Order.Status.PAID:
        return False
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    if payment_intent_id:
        order.stripe_payment_intent_id = payment_intent_id
    order.save(
        update_fields=[
            "status",
            "paid_at",
            "stripe_payment_intent_id",
            "updated_at",
        ]
    )
    send_order_confirmation(order)
    return True
