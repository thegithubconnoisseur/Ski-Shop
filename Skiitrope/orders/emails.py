import logging

from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_order_notification(order):
    """Alert the shop owner (ORDER_NOTIFICATION_EMAIL) that an order was placed."""
    if not settings.ORDER_NOTIFICATION_EMAIL:
        return False

    context = {"order": order, "items": order.items.all()}
    subject = f"New order {order.number} placed — ${order.total}"
    body = render_to_string("orders/emails/order_notification.txt", context)

    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.SERVER_EMAIL,
        to=[settings.ORDER_NOTIFICATION_EMAIL],
        reply_to=[order.email],
    )

    try:
        message.send()
    except Exception:
        logger.exception("Order notification failed for order %s", order.number)
        return False
    return True


def send_order_confirmation(order):
    """Email the customer a confirmation for a paid order (via Mailgun)."""
    if order.confirmation_email_sent:
        return False

    context = {"order": order, "items": order.items.all()}
    subject = f"Your Skiitrope order {order.number} is confirmed"
    text_body = render_to_string("orders/emails/order_confirmation.txt", context)
    html_body = render_to_string("orders/emails/order_confirmation.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.email],
        reply_to=[settings.DEFAULT_FROM_EMAIL],
    )
    message.attach_alternative(html_body, "text/html")

    try:
        message.send()
    except Exception:
        logger.exception("Confirmation email failed for order %s", order.number)
        return False

    order.confirmation_email_sent = True
    order.save(update_fields=["confirmation_email_sent"])
    return True
