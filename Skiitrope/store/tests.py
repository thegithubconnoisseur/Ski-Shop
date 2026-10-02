from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from .models import Category, Product


class ProductModelTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Snowboards")
        self.product = Product.objects.create(
            category=self.category,
            name="Nightride 156",
            price=Decimal("499.00"),
            stock=4,
        )

    def test_slug_is_generated_from_name(self):
        self.assertEqual(self.product.slug, "nightride-156")

    def test_in_stock_true_when_stock_positive(self):
        self.assertTrue(self.product.in_stock)

    def test_in_stock_false_when_stock_zero(self):
        self.product.stock = 0
        self.assertFalse(self.product.in_stock)

    def test_get_absolute_url(self):
        self.assertEqual(
            self.product.get_absolute_url(),
            reverse("store:product_detail", args=[self.product.slug]),
        )


class StoreViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.skis = Category.objects.create(name="Skis", slug="skis", sort_order=1)
        cls.apparel = Category.objects.create(name="Apparel", slug="apparel", sort_order=2)
        cls.featured = Product.objects.create(
            category=cls.skis,
            name="Glacier Peak 178",
            price=Decimal("649.00"),
            stock=5,
            is_featured=True,
        )
        cls.regular = Product.objects.create(
            category=cls.apparel,
            name="Powder Shell Jacket",
            price=Decimal("279.00"),
            stock=10,
        )

    def test_home_lists_featured_products(self):
        response = self.client.get(reverse("store:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Featured gear")
        self.assertContains(response, "Glacier Peak 178")

    def test_home_fills_featured_grid_when_not_enough_featured(self):
        response = self.client.get(reverse("store:home"))
        self.assertContains(response, "Powder Shell Jacket")

    def test_product_list_shows_all_active_products(self):
        response = self.client.get(reverse("store:product_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Glacier Peak 178")
        self.assertContains(response, "Powder Shell Jacket")

    def test_product_list_hides_inactive_products(self):
        Product.objects.create(
            category=self.skis,
            name="Retired Board",
            price=Decimal("99.00"),
            stock=1,
            is_active=False,
        )
        response = self.client.get(reverse("store:product_list"))
        self.assertNotContains(response, "Retired Board")

    def test_product_list_filters_by_category(self):
        response = self.client.get(reverse("store:product_list"), {"category": "skis"})
        self.assertContains(response, "Glacier Peak 178")
        self.assertNotContains(response, "Powder Shell Jacket")

    def test_product_list_search(self):
        response = self.client.get(reverse("store:product_list"), {"q": "glacier"})
        self.assertContains(response, "Glacier Peak 178")
        self.assertNotContains(response, "Powder Shell Jacket")

    def test_product_detail(self):
        response = self.client.get(self.featured.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Glacier Peak 178")
        self.assertContains(response, "649.00")

    def test_product_detail_404_for_inactive(self):
        retired = Product.objects.create(
            category=self.skis,
            name="Retired Board",
            price=Decimal("99.00"),
            stock=1,
            is_active=False,
        )
        response = self.client.get(retired.get_absolute_url())
        self.assertEqual(response.status_code, 404)
