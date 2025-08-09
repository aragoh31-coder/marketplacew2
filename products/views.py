from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.db import models

from .models import Category, Product


def product_list(request):
    products = Product.objects.filter(is_available=True).select_related("vendor", "category")
    categories = Category.objects.all()

    category_filter = request.GET.get("category") or ""
    if category_filter:
        products = products.filter(category_id=category_filter)

    q = (request.GET.get("q") or "").strip()
    if q:
        products = products.filter(models.Q(name__icontains=q) | models.Q(description__icontains=q))

    min_price = request.GET.get("min_price")
    max_price = request.GET.get("max_price")
    try:
        if min_price not in (None, "",):
            products = products.filter(price_btc__gte=min_price)
        if max_price not in (None, "",):
            products = products.filter(price_btc__lte=max_price)
    except Exception:
        pass

    paginator = Paginator(products, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "products/list.html",
        {
            "page_obj": page_obj,
            "categories": categories,
            "selected_category": category_filter,
            "q": q,
            "min_price": min_price or "",
            "max_price": max_price or "",
        },
    )


def product_detail(request, pk):
    product = get_object_or_404(Product.objects.select_related("vendor", "category"), pk=pk, is_available=True)
    return render(request, "products/detail.html", {"product": product})


def products_by_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    products = Product.objects.filter(category=category, is_available=True).select_related("vendor", "category")

    paginator = Paginator(products, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request, "products/list.html", {"page_obj": page_obj, "category": category}
    )
