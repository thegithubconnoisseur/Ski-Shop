import jwt as pyjwt
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.shortcuts import get_object_or_404
from jwt import PyJWKClient
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from allauth.socialaccount.models import SocialAccount
from cart.cart import DbCart, get_cart
from orders import payments
from orders.forms import CheckoutForm
from orders.models import Order
from orders.services import create_order_from_cart
from store.models import Category, Product

from .serializers import (
    CategorySerializer,
    OrderSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    UserSerializer,
    cart_payload,
)

User = get_user_model()

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"


class GoogleAuthError(Exception):
    """Raised when a Google ID token fails verification."""


def verify_google_id_token(id_token):
    """Verify a Google ID token against Google's public keys.

    The app obtains the token from Google directly, so signature, audience,
    issuer and expiry all have to be checked here before trusting the
    identity.
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise GoogleAuthError("Google sign-in is not configured.")
    try:
        signing_key = PyJWKClient(GOOGLE_JWKS_URL).get_signing_key_from_jwt(id_token)
        payload = pyjwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.GOOGLE_CLIENT_ID,
            issuer="https://accounts.google.com",
        )
    except pyjwt.PyJWTError as exc:
        raise GoogleAuthError("Google sign-in failed.") from exc
    if not payload.get("email") or not payload.get("email_verified"):
        raise GoogleAuthError("Google account has no verified email.")
    return payload


def get_or_create_google_user(payload):
    """Resolve the Google identity to a local account.

    Matching runs on the Google `sub` first (a stable per-account id) so the
    same Google account always lands on the same user — including accounts
    created earlier through the website's Google login.
    """
    uid = payload["sub"]
    account = SocialAccount.objects.filter(provider="google", uid=uid).first()
    if account:
        return account.user

    email = payload["email"].lower()
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        user = User.objects.create_user(email, None)
    if not user.first_name and payload.get("given_name"):
        user.first_name = payload["given_name"]
        user.save(update_fields=["first_name"])
    if not user.last_name and payload.get("family_name"):
        user.last_name = payload["family_name"]
        user.save(update_fields=["last_name"])

    SocialAccount.objects.get_or_create(
        user=user,
        provider="google",
        uid=uid,
        defaults={"extra_data": {"email": email, "name": payload.get("name", "")}},
    )
    return user


@api_view(["GET"])
@permission_classes([AllowAny])
def product_list(request):
    products = Product.objects.filter(is_active=True).select_related("category")
    category_slug = request.query_params.get("category", "").strip()
    query = request.query_params.get("q", "").strip()
    if category_slug:
        products = products.filter(category__slug=category_slug)
    if query:
        products = products.filter(name__icontains=query)
    serializer = ProductListSerializer(
        products, many=True, context={"request": request}
    )
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("category"), slug=slug, is_active=True
    )
    serializer = ProductDetailSerializer(product, context={"request": request})
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def category_list(request):
    serializer = CategorySerializer(Category.objects.all(), many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def cart_detail(request):
    return Response(cart_payload(get_cart(request), request))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cart_add(request):
    product = get_object_or_404(
        Product, id=request.data.get("product_id"), is_active=True
    )
    cart = get_cart(request)
    quantity = _clean_quantity(request.data.get("quantity", 1), product)
    cart.add(product, quantity=quantity, override=True)
    return Response(cart_payload(cart, request))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cart_update(request):
    product = get_object_or_404(Product, id=request.data.get("product_id"))
    cart = get_cart(request)
    try:
        quantity = int(request.data.get("quantity", 1))
    except (TypeError, ValueError):
        return Response(
            {"detail": "Invalid quantity."}, status=status.HTTP_400_BAD_REQUEST
        )
    if quantity < 1:
        cart.remove(product)
    else:
        cart.add(product, quantity=_clean_quantity(quantity, product), override=True)
    return Response(cart_payload(cart, request))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cart_remove(request):
    product = get_object_or_404(Product, id=request.data.get("product_id"))
    get_cart(request).remove(product)
    return Response(cart_payload(get_cart(request), request))


@api_view(["POST"])
@permission_classes([AllowAny])
def google_auth(request):
    id_token = request.data.get("id_token") or ""
    if not str(id_token).strip():
        return Response(
            {"detail": "id_token is required."}, status=status.HTTP_400_BAD_REQUEST
        )
    try:
        payload = verify_google_id_token(id_token)
    except GoogleAuthError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_401_UNAUTHORIZED)

    user = get_or_create_google_user(payload)
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": UserSerializer(user).data})


@api_view(["POST"])
@permission_classes([AllowAny])
def email_login(request):
    user = authenticate(
        request,
        email=(request.data.get("email") or "").strip(),
        password=request.data.get("password") or "",
    )
    if user is None:
        return Response(
            {"detail": "Invalid email or password."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    token, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token.key, "user": UserSerializer(user).data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def checkout(request):
    cart = DbCart(request.user)
    if not cart:
        return Response(
            {"detail": "Your cart is empty."}, status=status.HTTP_400_BAD_REQUEST
        )
    if not payments.stripe_configured():
        return Response(
            {"detail": "Payments are not configured."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    form = CheckoutForm(request.data)
    if not form.is_valid():
        return Response(
            {"detail": "Invalid checkout details.", "errors": form.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )
    order = create_order_from_cart(cart, form, request.user)
    session = payments.create_checkout_session(order, request)
    order.stripe_session_id = session.id
    order.save(update_fields=["stripe_session_id", "updated_at"])
    return Response({"checkout_url": session.url, "order_number": order.number})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_list(request):
    orders = Order.objects.filter(user=request.user).prefetch_related("items")
    return Response(OrderSerializer(orders, many=True).data)


def _clean_quantity(value, product):
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        quantity = 1
    quantity = max(quantity, 1)
    if product.stock:
        quantity = min(quantity, product.stock)
    return quantity
