from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from store.models import Product

from .cart import CART_SESSION_KEY, DbCart


@receiver(user_logged_in)
def merge_session_cart_into_account(sender, request, user, **kwargs):
    """Fold an anonymous session cart into the account's database cart.

    Runs for every login (email or Google, on the website), so a cart built
    while browsing logged-out follows the account to every other device —
    the mobile app included.
    """
    if request is None:
        return
    session_cart = request.session.get(CART_SESSION_KEY)
    if not isinstance(session_cart, dict) or not session_cart:
        return
    cart = DbCart(user)
    for key, item in session_cart.items():
        product = Product.objects.filter(pk=key, is_active=True).first()
        if product is not None:
            cart.add(product, quantity=item.get("quantity", 1))
    request.session[CART_SESSION_KEY] = {}
    request.session.modified = True
