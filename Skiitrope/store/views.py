from django.shortcuts import get_object_or_404, render

from .models import Category, Product


def home(request):
    featured = Product.objects.filter(is_active=True, is_featured=True)[:4]
    if len(featured) < 4:
        extra = Product.objects.filter(is_active=True).exclude(
            id__in=[p.id for p in featured]
        )[: 4 - len(featured)]
        featured = list(featured) + list(extra)
    return render(
        request,
        "home.html",
        {
            "categories": Category.objects.all(),
            "featured_products": featured,
        },
    )


def product_list(request):
    products = Product.objects.filter(is_active=True).select_related("category")
    categories = Category.objects.all()

    category_slug = request.GET.get("category", "").strip()
    query = request.GET.get("q", "").strip()

    current_category = None
    if category_slug:
        current_category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=current_category)
    if query:
        products = products.filter(name__icontains=query)

    return render(
        request,
        "store/product_list.html",
        {
            "products": products,
            "categories": categories,
            "current_category": current_category,
            "query": query,
        },
    )


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("category"), slug=slug, is_active=True
    )
    related = (
        Product.objects.filter(category=product.category, is_active=True)
        .exclude(id=product.id)[:4]
    )
    return render(
        request,
        "store/product_detail.html",
        {"product": product, "related_products": related},
    )
