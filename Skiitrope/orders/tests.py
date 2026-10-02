from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from cart.cart import Cart
from store.models import Category, Product

from .forms import CheckoutForm
from .models import Order
from .payments import mark_order_paid
from .services import create_order_from_cart

STRIPE_TEST_SETTINGS = {
    "STRIPE_SECRET_KEY": "sk_test_fake",
    "STRIPE_WEBHOOK_SECRET": "whsec_fake",
    "ORDER_NOTIFICATION_EMAIL": "",
}


def session_cart(session):
    return Cart(SimpleNamespace(session=session))


def make_product(**overrides):
    defaults = {
        "category": Category.objects.get_or_create(name="Snowboards")[0],
        "name": "Nightride 156",
        "price": Decimal("100.00"),
        "stock": 10,
    }
    defaults.update(overrides)
    return Product.objects.create(**defaults)


CHECKOUT_PAYLOAD = {
    "email": "rider@example.com",
    "full_name": "Ava Rider",
    "phone": "+234 800 000 0000",
    "address_line1": "12 Slope Street",
    "address_line2": "",
    "city": "Lagos",
    "state": "Lagos",
    "postal_code": "100001",
    "country": "NG",
}


class OrderServiceTests(TestCase):
    def setUp(self):
        self.product = make_product()
        self.cheap = make_product(name="Cheap Cap", price=Decimal("20.00"))

    def fill_cart(self, quantity=2):
        cart = session_cart(self.client.session)
        cart.add(self.product, quantity=quantity)
        return cart

    def test_create_order_snapshots_cart(self):
        cart = self.fill_cart()
        form = CheckoutForm(CHECKOUT_PAYLOAD)
        self.assertTrue(form.is_valid(), form.errors)
        order = create_order_from_cart(cart, form)

        self.assertTrue(order.number.startswith("SK-"))
        self.assertEqual(order.subtotal, Decimal("200.00"))
        self.assertEqual(order.shipping, Decimal("15.00"))
        self.assertEqual(order.total, Decimal("215.00"))
        self.assertEqual(order.currency, "USD")
        self.assertEqual(order.status, Order.Status.PENDING)

        item = order.items.get()
        self.assertEqual(item.product_name, "Nightride 156")
        self.assertEqual(item.unit_price, Decimal("100.00"))
        self.assertEqual(item.quantity, 2)

    def test_item_survives_product_deletion(self):
        cart = self.fill_cart()
        form = CheckoutForm(CHECKOUT_PAYLOAD)
        order = create_order_from_cart(cart, form)
        self.product.delete()
        item = order.items.get()
        self.assertIsNone(item.product)
        self.assertEqual(item.product_name, "Nightride 156")


@override_settings(ORDER_NOTIFICATION_EMAIL="")
class MarkPaidTests(TestCase):
    def setUp(self):
        cart = session_cart(self.client.session)
        cart.add(make_product(), quantity=1)
        form = CheckoutForm(CHECKOUT_PAYLOAD)
        form.is_valid()
        self.order = create_order_from_cart(cart, form)

    def test_marks_paid_and_emails_once(self):
        self.assertTrue(mark_order_paid(self.order, "pi_123"))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertIsNotNone(self.order.paid_at)
        self.assertEqual(self.order.stripe_payment_intent_id, "pi_123")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.order.number, mail.outbox[0].subject)
        self.assertIn("rider@example.com", mail.outbox[0].to)

    def test_idempotent(self):
        mark_order_paid(self.order, "pi_123")
        self.assertFalse(mark_order_paid(self.order, "pi_123"))
        self.assertEqual(len(mail.outbox), 1)

    def test_confirmation_email_contains_order_details(self):
        mark_order_paid(self.order, "pi_123")
        body = mail.outbox[0].body
        self.assertIn(self.order.number, body)
        self.assertIn("Nightride 156", body)
        self.assertIn("Ava Rider", body)


class OrderNotificationTests(TestCase):
    def place_order(self):
        cart = session_cart(self.client.session)
        cart.add(make_product(), quantity=1)
        form = CheckoutForm(CHECKOUT_PAYLOAD)
        form.is_valid()
        return create_order_from_cart(cart, form)

    @override_settings(ORDER_NOTIFICATION_EMAIL="owner@example.com")
    def test_owner_notified_when_order_placed(self):
        order = self.place_order()

        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["owner@example.com"])
        self.assertIn(order.number, message.subject)
        self.assertIn("Nightride 156", message.body)
        self.assertIn("Ava Rider", message.body)
        self.assertIn("rider@example.com", message.reply_to)

    @override_settings(ORDER_NOTIFICATION_EMAIL="")
    def test_no_notification_when_unconfigured(self):
        self.place_order()
        self.assertEqual(len(mail.outbox), 0)


@override_settings(**STRIPE_TEST_SETTINGS)
class CheckoutViewTests(TestCase):
    def setUp(self):
        self.product = make_product()
        self.add_url = reverse("cart:cart_add", args=[self.product.id])

    def test_empty_cart_redirects(self):
        response = self.client.get(reverse("orders:checkout"))
        self.assertRedirects(response, reverse("cart:cart_detail"))

    def test_get_renders_form(self):
        self.client.post(self.add_url, {"quantity": 1})
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="email"')
        self.assertContains(response, "Nightride 156")

    @patch("orders.payments.stripe.checkout.Session.create")
    def test_post_creates_order_and_redirects_to_stripe(self, mock_create):
        mock_create.return_value = MagicMock(id="cs_test_1", url="https://stripe.test/pay")
        self.client.post(self.add_url, {"quantity": 2})

        response = self.client.post(reverse("orders:checkout"), CHECKOUT_PAYLOAD)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "https://stripe.test/pay")

        order = Order.objects.get()
        self.assertEqual(order.stripe_session_id, "cs_test_1")
        self.assertEqual(order.total, Decimal("215.00"))

        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs["mode"], "payment")
        self.assertEqual(kwargs["customer_email"], "rider@example.com")
        self.assertEqual(kwargs["metadata"]["order_number"], order.number)
        line_items = kwargs["line_items"]
        self.assertEqual(line_items[0]["price_data"]["currency"], "usd")
        self.assertEqual(line_items[0]["price_data"]["unit_amount"], 10000)
        self.assertEqual(line_items[-1]["price_data"]["product_data"]["name"], "Shipping")

    @patch("orders.payments.stripe.checkout.Session.create")
    def test_invalid_form_rerenders_without_order(self, mock_create):
        self.client.post(self.add_url, {"quantity": 1})
        payload = dict(CHECKOUT_PAYLOAD, email="not-an-email")
        response = self.client.post(reverse("orders:checkout"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())
        mock_create.assert_not_called()

    def test_unconfigured_payments_shows_error(self):
        with override_settings(STRIPE_SECRET_KEY=""):
            self.client.post(self.add_url, {"quantity": 1})
            response = self.client.post(reverse("orders:checkout"), CHECKOUT_PAYLOAD, follow=True)
            self.assertContains(response, "Payments are not configured")
            self.assertFalse(Order.objects.exists())


@override_settings(**STRIPE_TEST_SETTINGS)
class CheckoutSuccessTests(TestCase):
    def setUp(self):
        self.product = make_product()
        cart = session_cart(self.client.session)
        cart.add(self.product, quantity=1)
        form = CheckoutForm(CHECKOUT_PAYLOAD)
        form.is_valid()
        self.order = create_order_from_cart(cart, form)
        self.order.stripe_session_id = "cs_test_1"
        self.order.save(update_fields=["stripe_session_id"])

    @patch("orders.payments.stripe.checkout.Session.retrieve")
    def test_paid_session_marks_paid_and_clears_cart(self, mock_retrieve):
        mock_retrieve.return_value = MagicMock(payment_status="paid", payment_intent="pi_9")
        response = self.client.get(
            reverse("orders:checkout_success"), {"session_id": "cs_test_1"}
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(len(session_cart(self.client.session)), 0)

    @patch("orders.payments.stripe.checkout.Session.retrieve")
    def test_unpaid_session_warns(self, mock_retrieve):
        mock_retrieve.return_value = MagicMock(payment_status="unpaid", payment_intent=None)
        response = self.client.get(
            reverse("orders:checkout_success"), {"session_id": "cs_test_1"}, follow=True
        )
        self.assertContains(response, "could not confirm this payment")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    @patch("orders.payments.stripe.checkout.Session.retrieve")
    def test_stripe_error_does_not_crash(self, mock_retrieve):
        import stripe

        mock_retrieve.side_effect = stripe.StripeError("boom")
        response = self.client.get(
            reverse("orders:checkout_success"), {"session_id": "cs_test_1"}
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)


@override_settings(**STRIPE_TEST_SETTINGS)
class StripeWebhookTests(TestCase):
    def setUp(self):
        cart = session_cart(self.client.session)
        cart.add(make_product(), quantity=1)
        form = CheckoutForm(CHECKOUT_PAYLOAD)
        form.is_valid()
        self.order = create_order_from_cart(cart, form)
        self.order.stripe_session_id = "cs_test_1"
        self.order.save(update_fields=["stripe_session_id"])
        self.url = reverse("orders:stripe_webhook")

    def event(self, payment_status="paid"):
        return {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_1",
                    "payment_status": payment_status,
                    "payment_intent": "pi_42",
                    "metadata": {"order_number": self.order.number},
                }
            },
        }

    @patch("orders.views.stripe.Webhook.construct_event")
    def test_completed_session_marks_order_paid(self, mock_construct):
        mock_construct.return_value = self.event()
        response = self.client.post(self.url, data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertEqual(self.order.stripe_payment_intent_id, "pi_42")
        self.assertEqual(len(mail.outbox), 1)

    @patch("orders.views.stripe.Webhook.construct_event")
    def test_duplicate_webhook_is_idempotent(self, mock_construct):
        mock_construct.return_value = self.event()
        self.client.post(self.url, data="{}", content_type="application/json")
        self.client.post(self.url, data="{}", content_type="application/json")
        self.assertEqual(len(mail.outbox), 1)

    @patch("orders.views.stripe.Webhook.construct_event")
    def test_unpaid_session_not_marked(self, mock_construct):
        mock_construct.return_value = self.event(payment_status="unpaid")
        response = self.client.post(self.url, data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PENDING)

    @patch("orders.views.stripe.Webhook.construct_event")
    def test_bad_signature_rejected(self, mock_construct):
        import stripe

        mock_construct.side_effect = stripe.SignatureVerificationError("bad", "sig")
        response = self.client.post(self.url, data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    @patch("orders.views.stripe.Webhook.construct_event")
    def test_get_not_allowed(self, mock_construct):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_unconfigured_returns_503(self):
        with override_settings(STRIPE_SECRET_KEY=""):
            response = self.client.post(self.url, data="{}", content_type="application/json")
            self.assertEqual(response.status_code, 503)


class CheckoutCancelledTests(TestCase):
    def test_renders(self):
        response = self.client.get(reverse("orders:checkout_cancelled"))
        self.assertEqual(response.status_code, 200)
