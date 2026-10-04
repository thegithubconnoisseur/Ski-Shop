from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from allauth.socialaccount.models import SocialAccount
from cart.models import CartItem
from orders.models import Order
from store.models import Category, Product

from .views import GoogleAuthError

User = get_user_model()

PASSWORD = "pass12345"

STRIPE_TEST_SETTINGS = {
    "STRIPE_SECRET_KEY": "sk_test_fake",
    "ORDER_NOTIFICATION_EMAIL": "",
}


def make_product(**overrides):
    defaults = {
        "category": Category.objects.get_or_create(name="Skis")[0],
        "name": "Glacier Peak 178",
        "price": Decimal("200.00"),
        "stock": 10,
    }
    defaults.update(overrides)
    return Product.objects.create(**defaults)


def make_user(email="shopper@example.com"):
    return User.objects.create_user(email, PASSWORD)


def auth_client(user):
    token = Token.objects.create(user=user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
    return client


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


def google_payload(**overrides):
    payload = {
        "sub": "google-uid-123",
        "email": "skiier@gmail.com",
        "email_verified": True,
        "given_name": "Ada",
        "family_name": "Lovelace",
        "name": "Ada Lovelace",
    }
    payload.update(overrides)
    return payload


class ProductApiTests(TestCase):
    def test_list_returns_active_products(self):
        make_product()
        make_product(name="Hidden", is_active=False)

        response = self.client.get("/api/products/")

        self.assertEqual(response.status_code, 200)
        results = response.json()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Glacier Peak 178")
        self.assertEqual(results[0]["price"], "200.00")
        self.assertEqual(results[0]["category"]["name"], "Skis")
        self.assertTrue(results[0]["in_stock"])

    def test_filter_by_category_slug(self):
        boards = Category.objects.get_or_create(name="Boards")[0]
        make_product()
        Product.objects.create(
            category=boards, name="Nightride 156", price=Decimal("100.00")
        )

        response = self.client.get("/api/products/", {"category": "boards"})

        self.assertEqual([p["name"] for p in response.json()], ["Nightride 156"])

    def test_search_by_name(self):
        make_product()
        make_product(name="Powder Beanie", price=Decimal("15.00"))

        response = self.client.get("/api/products/", {"q": "beanie"})

        self.assertEqual([p["name"] for p in response.json()], ["Powder Beanie"])

    def test_detail_includes_description(self):
        product = make_product(description="All-mountain freeride ski.")

        response = self.client.get(f"/api/products/{product.slug}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["description"], "All-mountain freeride ski."
        )

    def test_unknown_slug_404(self):
        response = self.client.get("/api/products/nope/")
        self.assertEqual(response.status_code, 404)


class CategoryApiTests(TestCase):
    def test_list(self):
        Category.objects.get_or_create(name="Skis")

        response = self.client.get("/api/categories/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([c["name"] for c in response.json()], ["Skis"])


class CartApiTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client = auth_client(self.user)
        self.product = make_product()

    def test_cart_requires_authentication(self):
        response = APIClient().get("/api/cart/")
        self.assertEqual(response.status_code, 401)

    def test_empty_cart(self):
        response = self.client.get("/api/cart/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["items"], [])
        self.assertEqual(data["count"], 0)
        self.assertEqual(data["currency"], "USD")
        self.assertEqual(data["currency_symbol"], "$")

    def test_add_returns_full_cart(self):
        response = self.client.post(
            "/api/cart/add/",
            {"product_id": self.product.id, "quantity": 2},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 2)
        self.assertEqual(data["subtotal"], "400.00")
        self.assertEqual(data["shipping"], "0.00")  # 400 >= 300: free shipping
        self.assertEqual(data["total"], "400.00")
        self.assertEqual(data["items"][0]["product"]["name"], "Glacier Peak 178")
        self.assertEqual(data["items"][0]["quantity"], 2)

    def test_add_clamps_quantity_to_stock(self):
        response = self.client.post(
            "/api/cart/add/",
            {"product_id": self.product.id, "quantity": 99},
            format="json",
        )
        self.assertEqual(response.json()["count"], 10)

    def test_add_unknown_product_404(self):
        response = self.client.post(
            "/api/cart/add/", {"product_id": 999}, format="json"
        )
        self.assertEqual(response.status_code, 404)

    def test_update_quantity(self):
        self.client.post(
            "/api/cart/add/", {"product_id": self.product.id, "quantity": 2},
            format="json",
        )
        response = self.client.post(
            "/api/cart/update/",
            {"product_id": self.product.id, "quantity": 5},
            format="json",
        )
        self.assertEqual(response.json()["count"], 5)

    def test_update_below_one_removes(self):
        self.client.post(
            "/api/cart/add/", {"product_id": self.product.id, "quantity": 2},
            format="json",
        )
        response = self.client.post(
            "/api/cart/update/",
            {"product_id": self.product.id, "quantity": 0},
            format="json",
        )
        self.assertEqual(response.json()["count"], 0)

    def test_remove(self):
        self.client.post(
            "/api/cart/add/", {"product_id": self.product.id, "quantity": 1},
            format="json",
        )
        response = self.client.post(
            "/api/cart/remove/", {"product_id": self.product.id}, format="json"
        )
        self.assertEqual(response.json()["count"], 0)
        self.assertEqual(CartItem.objects.filter(user=self.user).count(), 0)

    def test_cart_is_per_account(self):
        other = make_user("other@example.com")
        self.client.post(
            "/api/cart/add/", {"product_id": self.product.id, "quantity": 1},
            format="json",
        )
        self.assertEqual(CartItem.objects.filter(user=other).count(), 0)


class GoogleAuthApiTests(TestCase):
    def post_id_token(self):
        return self.client.post(
            "/api/auth/google/", {"id_token": "fake-id-token"}, format="json"
        )

    @patch("api.views.verify_google_id_token")
    def test_creates_user_social_account_and_token(self, verify):
        verify.return_value = google_payload()

        response = self.post_id_token()

        self.assertEqual(response.status_code, 200)
        data = response.json()
        user = User.objects.get(email="skiier@gmail.com")
        self.assertEqual(data["token"], Token.objects.get(user=user).key)
        self.assertEqual(data["user"]["first_name"], "Ada")
        self.assertTrue(
            SocialAccount.objects.filter(
                provider="google", uid="google-uid-123", user=user
            ).exists()
        )

    @patch("api.views.verify_google_id_token")
    def test_same_google_account_reuses_user_and_token(self, verify):
        verify.return_value = google_payload()

        first = self.post_id_token().json()
        second = self.post_id_token().json()

        self.assertEqual(first["token"], second["token"])
        self.assertEqual(User.objects.count(), 1)

    @patch("api.views.verify_google_id_token")
    def test_links_existing_account_created_on_the_website(self, verify):
        user = make_user("skiier@gmail.com")
        verify.return_value = google_payload()

        self.post_id_token()

        self.assertEqual(User.objects.count(), 1)
        self.assertTrue(
            SocialAccount.objects.filter(user=user, uid="google-uid-123").exists()
        )

    @patch("api.views.verify_google_id_token", side_effect=GoogleAuthError("bad"))
    def test_invalid_token_returns_401(self, _verify):
        response = self.post_id_token()
        self.assertEqual(response.status_code, 401)

    def test_missing_id_token_returns_400(self):
        response = self.client.post("/api/auth/google/", {}, format="json")
        self.assertEqual(response.status_code, 400)


class EmailLoginApiTests(TestCase):
    def test_login_returns_token(self):
        user = make_user()

        response = self.client.post(
            "/api/auth/login/",
            {"email": "shopper@example.com", "password": PASSWORD},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["token"], Token.objects.get(user=user).key)

    def test_wrong_password_rejected(self):
        make_user()

        response = self.client.post(
            "/api/auth/login/",
            {"email": "shopper@example.com", "password": "wrong"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)


@override_settings(**STRIPE_TEST_SETTINGS)
class CheckoutApiTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client = auth_client(self.user)
        self.product = make_product()
        self.client.post(
            "/api/cart/add/", {"product_id": self.product.id, "quantity": 1},
            format="json",
        )

    @patch("orders.payments.create_checkout_session")
    def test_checkout_returns_stripe_url_and_creates_order(self, create_session):
        create_session.return_value = SimpleNamespace(
            id="cs_test_1", url="https://stripe.test/pay"
        )

        response = self.client.post("/api/checkout/", CHECKOUT_PAYLOAD, format="json")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["checkout_url"], "https://stripe.test/pay")

        order = Order.objects.get(number=data["order_number"])
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.total, Decimal("215.00"))
        self.assertEqual(order.stripe_session_id, "cs_test_1")
        self.assertEqual(order.items.count(), 1)

    def test_empty_cart_rejected(self):
        self.client.post(
            "/api/cart/remove/", {"product_id": self.product.id}, format="json"
        )

        response = self.client.post("/api/checkout/", CHECKOUT_PAYLOAD, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("empty", response.json()["detail"].lower())

    def test_invalid_address_rejected_without_order(self):
        payload = dict(CHECKOUT_PAYLOAD, city="")

        response = self.client.post("/api/checkout/", payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("city", response.json()["errors"])
        self.assertFalse(Order.objects.exists())

    def test_requires_authentication(self):
        response = APIClient().post("/api/checkout/", CHECKOUT_PAYLOAD, format="json")
        self.assertEqual(response.status_code, 401)


class OrderApiTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client = auth_client(self.user)

    def make_order(self, user, number=None):
        return Order.objects.create(
            user=user,
            email="rider@example.com",
            full_name="Ava Rider",
            address_line1="12 Slope Street",
            city="Lagos",
            country="NG",
            subtotal=Decimal("100.00"),
            shipping=Decimal("15.00"),
            total=Decimal("115.00"),
        )

    def test_lists_only_own_orders(self):
        mine = self.make_order(self.user)
        other = self.make_order(make_user("other@example.com"))

        response = self.client.get("/api/orders/")

        self.assertEqual(response.status_code, 200)
        numbers = [o["number"] for o in response.json()]
        self.assertIn(mine.number, numbers)
        self.assertNotIn(other.number, numbers)

    def test_includes_items_and_totals(self):
        order = self.make_order(self.user)
        order.items.create(
            product_name="Glacier Peak 178",
            unit_price=Decimal("100.00"),
            quantity=1,
        )

        data = self.client.get("/api/orders/").json()[0]

        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["total"], "115.00")
        self.assertEqual(data["items"][0]["product_name"], "Glacier Peak 178")
        self.assertEqual(data["items"][0]["line_total"], "100.00")

    def test_requires_authentication(self):
        self.assertEqual(APIClient().get("/api/orders/").status_code, 401)
