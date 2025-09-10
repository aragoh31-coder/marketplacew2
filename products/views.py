from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from .models import Product, Category


def product_list(request: HttpRequest) -> HttpResponse:
    """Displays a paginated list of all available products, with optional category filtering."""
    products = Product.objects.filter(is_available=True).select_related('vendor', 'category')
    categories = Category.objects.all()
    
    category_filter = request.GET.get('category')
    if category_filter:
        try:
            category_id = int(category_filter)
            products = products.filter(category_id=category_id)
        except (ValueError, TypeError):
            # If the category is not a valid integer, ignore the filter.
            pass
    
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'products/list.html', {
        'page_obj': page_obj,
        'categories': categories,
        'selected_category': category_filter
    })


def product_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Displays the detail page for a single product."""
    product = get_object_or_404(Product, pk=pk, is_available=True)
    return render(request, 'products/detail.html', {'product': product})


def products_by_category(request: HttpRequest, category_id: int) -> HttpResponse:
    """Displays a paginated list of products belonging to a specific category."""
    category = get_object_or_404(Category, id=category_id)
    products = Product.objects.filter(category=category, is_available=True)
    
    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'products/list.html', {
        'page_obj': page_obj,
        'category': category
    })
