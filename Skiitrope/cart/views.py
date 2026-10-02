from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from store.models import Product

from .cart import Cart


def cart_detail(request):
    return render(request, "cart/cart_detail.html")


@require_POST
def cart_add(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    cart = Cart(request)

    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1
    if quantity < 1:
        quantity = 1
    if product.stock and quantity > product.stock:
        quantity = product.stock
        messages.warning(
            request, f"Only {product.stock} of {product.name} left in stock."
        )

    cart.add(product, quantity=quantity, override=True)
    messages.success(request, f"{product.name} added to your cart.")

    next_url = request.POST.get("next") or product.get_absolute_url()
    if not next_url.startswith("/"):
        next_url = reverse("cart:cart_detail")
    return redirect(next_url)


@require_POST
def cart_update(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_active=True)
    cart = Cart(request)

    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        return HttpResponseBadRequest("Invalid quantity.")

    if quantity < 1:
        cart.remove(product)
        messages.info(request, f"{product.name} removed from your cart.")
    else:
        if product.stock and quantity > product.stock:
            quantity = product.stock
            messages.warning(
                request, f"Only {product.stock} of {product.name} left in stock."
            )
        cart.add(product, quantity=quantity, override=True)
        messages.success(request, "Cart updated.")

    return redirect("cart:cart_detail")


@require_POST
def cart_remove(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    Cart(request).remove(product)
    messages.info(request, f"{product.name} removed from your cart.")
    return redirect("cart:cart_detail")
