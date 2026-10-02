import logging

import stripe
from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from cart.cart import Cart

from . import payments
from .forms import CheckoutForm
from .models import Order
from .services import create_order_from_cart

logger = logging.getLogger(__name__)


def checkout(request):
    cart = Cart(request)
    if not cart:
        messages.info(request, "Your cart is empty — add something first.")
        return redirect("cart:cart_detail")

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            if not payments.stripe_configured():
                messages.error(
                    request,
                    "Payments are not configured yet. Add your Stripe keys to "
                    "the .env file to accept card payments.",
                )
            else:
                order = create_order_from_cart(cart, form, request.user)
                session = payments.create_checkout_session(order, request)
                order.stripe_session_id = session.id
                order.save(update_fields=["stripe_session_id", "updated_at"])
                return redirect(session.url, permanent=False)
    else:
        initial = {}
        if request.user.is_authenticated:
            initial = {
                "email": request.user.email,
                "full_name": request.user.get_full_name(),
            }
        form = CheckoutForm(initial=initial)

    return render(
        request,
        "orders/checkout.html",
        {"form": form, "payments_configured": payments.stripe_configured()},
    )


def checkout_success(request):
    session_id = request.GET.get("session_id", "").strip()
    order = None

    if session_id:
        order = Order.objects.filter(stripe_session_id=session_id).first()
        if order and payments.stripe_configured():
            try:
                session = payments.retrieve_checkout_session(session_id)
                if session.payment_status == "paid":
                    payments.mark_order_paid(order, session.payment_intent or "")
            except stripe.StripeError:
                logger.exception("Could not reconcile Stripe session %s", session_id)

    if order and order.status == Order.Status.PAID:
        Cart(request).clear()
    else:
        messages.warning(
            request,
            "We could not confirm this payment yet. If you were charged, the "
            "confirmation email will follow shortly.",
        )

    return render(request, "orders/checkout_success.html", {"order": order})


def checkout_cancelled(request):
    return render(request, "orders/checkout_cancelled.html")


@csrf_exempt
@require_POST
def stripe_webhook(request):
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET
    if not payments.stripe_configured() or not webhook_secret:
        return HttpResponse(status=503)

    try:
        event = stripe.Webhook.construct_event(
            request.body,
            request.META.get("HTTP_STRIPE_SIGNATURE", ""),
            webhook_secret,
        )
    except (ValueError, stripe.SignatureVerificationError):
        return HttpResponseBadRequest("Invalid payload or signature.")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        order = Order.objects.filter(
            number=(session["metadata"] or {}).get("order_number", ""),
            stripe_session_id=session["id"],
        ).first()
        if order and session["payment_status"] == "paid":
            payments.mark_order_paid(order, session.get("payment_intent") or "")

    return HttpResponse(status=200)
