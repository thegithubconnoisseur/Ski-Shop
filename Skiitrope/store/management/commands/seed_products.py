import shutil
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from store.models import Category, Product

SEED_IMAGE_DIR = settings.BASE_DIR / "static" / "img" / "products"

CATEGORIES = [
    ("Skis", "All-mountain, carving and powder skis for every level.", 1),
    ("Snowboards", "All-mountain and freestyle boards built to ride hard.", 2),
    ("Boots & Bindings", "Dialed-in boots and bindings for a locked-in ride.", 3),
    ("Apparel", "Shells and layers that keep you dry and warm.", 4),
    ("Accessories", "Goggles, helmets and the small stuff that matters.", 5),
]

PRODUCTS = [
    {
        "category": "Skis",
        "name": "Glacier Peak 178 All-Mountain Skis",
        "price": "649.00",
        "stock": 12,
        "featured": True,
        "image": "glacier-peak-skis.jpg",
        "description": (
            "A go-anywhere all-mountain ski with a poplar core and 96mm waist. "
            "Confident on groomers, floaty in fresh snow, and light enough for "
            "long touring days. Length 178cm, radius 18m."
        ),
    },
    {
        "category": "Skis",
        "name": "Summit Carve 165 Racing Skis",
        "price": "829.00",
        "stock": 6,
        "featured": False,
        "image": "summit-carve-skis.jpg",
        "description": (
            "Stiff, fast and precise. A double titanal racing ski for carving "
            "hardpack at speed. Length 165cm with a 15m turn radius for tight, "
            "confident arcs."
        ),
    },
    {
        "category": "Snowboards",
        "name": "Nightride 156 All-Mountain Snowboard",
        "price": "499.00",
        "stock": 10,
        "featured": True,
        "image": "nightride-snowboard.jpg",
        "description": (
            "A true all-mountain deck with a directional shape and hybrid "
            "camber. Stable at speed, playful in the trees. Size 156cm, "
            "recommended for riders 70–90kg."
        ),
    },
    {
        "category": "Snowboards",
        "name": "Redline 152 Freestyle Snowboard",
        "price": "459.00",
        "stock": 8,
        "featured": False,
        "image": "redline-snowboard.jpg",
        "description": (
            "Park-ready twin tip with a soft flex and true twin shape. "
            "Butters, presses and rails all day. Size 152cm."
        ),
    },
    {
        "category": "Boots & Bindings",
        "name": "Alpine Pro 100 Ski Boots",
        "price": "329.00",
        "stock": 14,
        "featured": True,
        "image": "alpine-pro-boots.jpg",
        "description": (
            "100-flex all-mountain boots with a heat-moldable liner and four "
            "micro-adjustable buckles. Comfortable from first chair to last. "
            "Sizes 25.5–30.5."
        ),
    },
    {
        "category": "Boots & Bindings",
        "name": "Ridge Snowboard Boots",
        "price": "249.00",
        "stock": 15,
        "featured": False,
        "image": "ridge-boots.jpg",
        "description": (
            "Medium-flex boots with a quick-lace system, grippy outsole and "
            "heat-moldable liner. All-day comfort, precise response."
        ),
    },
    {
        "category": "Apparel",
        "name": "Powder Shell Jacket",
        "price": "279.00",
        "stock": 20,
        "featured": True,
        "image": "powder-jacket.jpg",
        "description": (
            "20K/20K waterproof-breathable shell with a helmet-compatible hood, "
            "pit zips and a powder skirt. Black with red and blue zip accents."
        ),
    },
    {
        "category": "Accessories",
        "name": "Whiteout Goggles",
        "price": "129.00",
        "stock": 25,
        "featured": False,
        "image": "whiteout-goggles.jpg",
        "description": (
            "Toroidal lens with anti-fog coating and 100% UV protection. "
            "Includes a spare low-light lens. Helmet compatible."
        ),
    },
    {
        "category": "Accessories",
        "name": "Apex MIPS Helmet",
        "price": "189.00",
        "stock": 18,
        "featured": False,
        "image": "apex-helmet.jpg",
        "description": (
            "Lightweight in-mold helmet with MIPS rotational protection, "
            "adjustable venting and audio-ready earpads. Sizes S–XL."
        ),
    },
]


class Command(BaseCommand):
    help = "Seed the catalogue with Skiitrope demo categories and products."

    def handle(self, *args, **options):
        media_products = Path(settings.MEDIA_ROOT) / "products"
        media_products.mkdir(parents=True, exist_ok=True)

        categories = {}
        for name, description, sort_order in CATEGORIES:
            category, _ = Category.objects.update_or_create(
                name=name,
                defaults={"description": description, "sort_order": sort_order},
            )
            categories[name] = category
        self.stdout.write(f"Categories ready: {len(categories)}")

        created = updated = 0
        for data in PRODUCTS:
            image_name = data["image"]
            source = SEED_IMAGE_DIR / image_name
            target = media_products / image_name
            if source.exists() and not target.exists():
                shutil.copyfile(source, target)

            product, was_created = Product.objects.update_or_create(
                name=data["name"],
                defaults={
                    "category": categories[data["category"]],
                    "description": data["description"],
                    "price": Decimal(data["price"]),
                    "stock": data["stock"],
                    "is_featured": data["featured"],
                    "is_active": True,
                    "image": f"products/{image_name}" if target.exists() else "",
                },
            )
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(
            self.style.SUCCESS(f"Products: {created} created, {updated} updated.")
        )
