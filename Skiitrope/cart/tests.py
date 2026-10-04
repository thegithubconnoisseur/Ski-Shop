from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from store.models import Category, Product

from .cart import Cart, DbCart
from .models import CartItem

User = get_user_model()


def session_cart(session):
    return Cart(SimpleNamespace(session=session))


def make_product(**overrides):
    defaults = {
        "category": Category.objects.get_or_create(name="Skis")[0],
        "name": "Glacier Peak 178",
        "price": Decimal("200.00"),
        "stock": 10,
    }
    defaults.update(overrides)
    return Product.objects.create(**defaults)


class CartTests(TestCase):
    def setUp(self):
        self.product = make_product()
        self.cheap = make_product(name="Cheap Cap", price=Decimal("20.00"))
        self.session = self.client.session

    def get_cart(self):
        return session_cart(self.session)

    def test_add_and_count(self):
        cart = self.get_cart()
        cart.add(self.product, quantity=2)
        self.assertEqual(self.get_cart().count, 2)
        self.assertEqual(len(self.get_cart()), 1)
        self.assertTrue(self.get_cart())

    def test_add_caps_quantity_at_stock(self):
        product = make_product(name="Scarce Board", stock=3)
        cart = self.get_cart()
        cart.add(product, quantity=99)
        self.assertEqual(self.get_cart().cart[str(product.id)]["quantity"], 3)

    def test_add_accumulates_and_override(self):
        cart = self.get_cart()
        cart.add(self.product, quantity=1)
        cart.add(self.product, quantity=2)
        self.assertEqual(self.get_cart().cart[str(self.product.id)]["quantity"], 3)
        self.get_cart().add(self.product, quantity=5, override=True)
        self.assertEqual(self.get_cart().cart[str(self.product.id)]["quantity"], 5)

    def test_remove_and_clear(self):
        cart = self.get_cart()
        cart.add(self.product)
        cart.add(self.cheap)
        cart.remove(self.product)
        self.assertEqual(len(self.get_cart()), 1)
        self.get_cart().clear()
        self.assertEqual(len(self.get_cart()), 0)

    def test_subtotal_and_total_with_flat_shipping(self):
        cart = self.get_cart()
        cart.add(self.product, quantity=1)
        self.assertEqual(self.get_cart().subtotal, Decimal("200.00"))
        self.assertEqual(self.get_cart().shipping, Decimal("15.00"))
        self.assertEqual(self.get_cart().total, Decimal("215.00"))

    def test_free_shipping_over_threshold(self):
        cart = self.get_cart()
        cart.add(self.product, quantity=2)  # 400 >= 300
        self.assertEqual(self.get_cart().shipping, Decimal("0.00"))
        self.assertEqual(self.get_cart().free_shipping_remaining, Decimal("0.00"))

    def test_free_shipping_remaining(self):
        cart = self.get_cart()
        cart.add(self.product, quantity=1)  # 200; 100 more to free shipping
        self.assertEqual(self.get_cart().free_shipping_remaining, Decimal("100.00"))

    def test_iteration_prunes_removed_products(self):
        cart = self.get_cart()
        cart.add(self.product)
        cart.add(self.cheap)
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])
        rows = list(self.get_cart())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["product"], self.cheap)

    def test_iteration_totals(self):
        cart = self.get_cart()
        cart.add(self.cheap, quantity=3)
        row = list(self.get_cart())[0]
        self.assertEqual(row["total"], Decimal("60.00"))


class CartViewTests(TestCase):
    def setUp(self):
        self.product = make_product()

    def test_cart_detail_renders(self):
        response = self.client.get(reverse("cart:cart_detail"))
        self.assertEqual(response.status_code, 200)

    def test_add_requires_post(self):
        response = self.client.get(reverse("cart:cart_add", args=[self.product.id]))
        self.assertEqual(response.status_code, 405)

    def test_add_and_redirect_to_cart(self):
        response = self.client.post(
            reverse("cart:cart_add", args=[self.product.id]),
            {"quantity": 2, "next": reverse("cart:cart_detail")},
        )
        self.assertRedirects(response, reverse("cart:cart_detail"))
        self.assertEqual(self.get_cart().count, 2)

    def test_add_clamps_bad_quantity(self):
        self.client.post(
            reverse("cart:cart_add", args=[self.product.id]),
            {"quantity": "abc"},
        )
        self.assertEqual(self.get_cart().count, 1)

    def test_add_ignores_external_next(self):
        response = self.client.post(
            reverse("cart:cart_add", args=[self.product.id]),
            {"quantity": 1, "next": "https://evil.example.com"},
        )
        self.assertRedirects(response, reverse("cart:cart_detail"))

    def test_update_quantity(self):
        self.client.post(reverse("cart:cart_add", args=[self.product.id]), {"quantity": 1})
        self.client.post(
            reverse("cart:cart_update", args=[self.product.id]),
            {"quantity": 4},
        )
        self.assertEqual(self.get_cart().count, 4)

    def test_update_below_one_removes(self):
        self.client.post(reverse("cart:cart_add", args=[self.product.id]), {"quantity": 1})
        self.client.post(
            reverse("cart:cart_update", args=[self.product.id]),
            {"quantity": 0},
        )
        self.assertEqual(len(self.get_cart()), 0)

    def test_remove(self):
        self.client.post(reverse("cart:cart_add", args=[self.product.id]), {"quantity": 1})
        self.client.post(reverse("cart:cart_remove", args=[self.product.id]))
        self.assertEqual(len(self.get_cart()), 0)

    def get_cart(self):
        return session_cart(self.client.session)


class DbCartTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("shopper@example.com", "pass12345")
        self.product = make_product()
        self.cheap = make_product(name="Cheap Cap", price=Decimal("20.00"))

    def cart(self):
        return DbCart(self.user)

    def test_add_and_count(self):
        self.cart().add(self.product, quantity=2)
        self.assertEqual(self.cart().count, 2)
        self.assertEqual(len(self.cart()), 1)
        self.assertTrue(self.cart())

    def test_add_accumulates_and_override(self):
        self.cart().add(self.product, quantity=1)
        self.cart().add(self.product, quantity=2)
        self.assertEqual(self.cart().count, 3)
        self.cart().add(self.product, quantity=5, override=True)
        self.assertEqual(self.cart().count, 5)

    def test_add_caps_quantity_at_stock(self):
        product = make_product(name="Scarce Board", stock=3)
        self.cart().add(product, quantity=99)
        self.assertEqual(CartItem.objects.get(product=product).quantity, 3)

    def test_remove_and_clear(self):
        self.cart().add(self.product)
        self.cart().add(self.cheap)
        self.cart().remove(self.product)
        self.assertEqual(len(self.cart()), 1)
        self.cart().clear()
        self.assertEqual(len(self.cart()), 0)

    def test_totals_match_session_cart_math(self):
        self.cart().add(self.product, quantity=1)
        self.assertEqual(self.cart().subtotal, Decimal("200.00"))
        self.assertEqual(self.cart().shipping, Decimal("15.00"))
        self.assertEqual(self.cart().total, Decimal("215.00"))

    def test_free_shipping_over_threshold(self):
        self.cart().add(self.product, quantity=2)  # 400 >= 300
        self.assertEqual(self.cart().shipping, Decimal("0.00"))
        self.assertEqual(self.cart().free_shipping_remaining, Decimal("0.00"))

    def test_iteration_skips_and_prunes_inactive_products(self):
        self.cart().add(self.product)
        self.cart().add(self.cheap)
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])

        rows = list(self.cart())

        self.assertEqual([row["product"] for row in rows], [self.cheap])
        self.assertFalse(CartItem.objects.filter(product=self.product).exists())

    def test_rows_unique_per_user_and_product(self):
        DbCart(self.user).add(self.product, quantity=1)
        DbCart(self.user).add(self.product, quantity=1)
        self.assertEqual(CartItem.objects.count(), 1)

        other = User.objects.create_user("other@example.com", "pass12345")
        DbCart(other).add(self.product, quantity=1)
        self.assertEqual(CartItem.objects.count(), 2)


class LoginCartMergeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("shopper@example.com", "pass12345")
        self.product = make_product()
        self.cheap = make_product(name="Cheap Cap", price=Decimal("20.00"))

    def session_cart(self):
        return session_cart(self.client.session)

    def test_session_cart_merges_into_account_on_login(self):
        self.client.post(
            reverse("cart:cart_add", args=[self.product.id]), {"quantity": 2}
        )
        self.client.post(
            reverse("cart:cart_add", args=[self.cheap.id]), {"quantity": 1}
        )

        self.client.login(email="shopper@example.com", password="pass12345")

        cart = DbCart(self.user)
        self.assertEqual(cart.count, 3)
        self.assertEqual(CartItem.objects.filter(user=self.user).count(), 2)
        self.assertEqual(len(self.session_cart()), 0)

    def test_merge_accumulates_with_existing_account_cart(self):
        DbCart(self.user).add(self.product, quantity=1)
        self.client.post(
            reverse("cart:cart_add", args=[self.product.id]), {"quantity": 2}
        )

        self.client.login(email="shopper@example.com", password="pass12345")

        self.assertEqual(DbCart(self.user).count, 3)

    def test_logged_in_cart_adds_go_to_database_not_session(self):
        self.client.login(email="shopper@example.com", password="pass12345")

        self.client.post(
            reverse("cart:cart_add", args=[self.product.id]), {"quantity": 2}
        )

        self.assertEqual(DbCart(self.user).count, 2)
        self.assertEqual(len(self.session_cart()), 0)
