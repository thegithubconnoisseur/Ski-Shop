from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["product", "product_name", "unit_price", "quantity"]
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["number", "full_name", "email", "total", "currency", "status", "created_at"]
    list_filter = ["status", "currency", "country", "created_at"]
    search_fields = ["number", "email", "full_name"]
    readonly_fields = [
        "number",
        "stripe_session_id",
        "stripe_payment_intent_id",
        "paid_at",
        "confirmation_email_sent",
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "created_at"
    inlines = [OrderItemInline]
    fieldsets = (
        ("Order", {"fields": ("number", "status", "user", "created_at", "updated_at")}),
        ("Customer", {"fields": ("email", "full_name", "phone")}),
        ("Shipping address", {
            "fields": ("address_line1", "address_line2", "city", "state", "postal_code", "country")
        }),
        ("Amounts", {"fields": ("subtotal", "shipping", "total", "currency")}),
        ("Payment", {
            "fields": ("stripe_session_id", "stripe_payment_intent_id", "paid_at", "confirmation_email_sent")
        }),
    )
