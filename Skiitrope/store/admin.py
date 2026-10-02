from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "sort_order", "product_count"]
    list_editable = ["sort_order"]
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Products")
    def product_count(self, obj):
        return obj.products.count()


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "thumbnail",
        "name",
        "category",
        "price",
        "stock",
        "is_active",
        "is_featured",
    ]
    list_display_links = ["thumbnail", "name"]
    list_editable = ["price", "stock", "is_active", "is_featured"]
    list_filter = ["category", "is_active", "is_featured"]
    search_fields = ["name", "description"]
    prepopulated_fields = {"slug": ("name",)}

    @admin.display(description="Image")
    def thumbnail(self, obj):
        if not obj.image:
            return "—"
        return format_html(
            '<img src="{}" style="height:44px;border-radius:6px;" />', obj.image.url
        )
