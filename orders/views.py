from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Cart, CartItem, Order
from products.models import Product


@login_required
def cart_view(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
    cart_items = cart.items.select_related('product')
    return render(request, 'orders/cart.html', {'cart_items': cart_items})


@login_required
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id, is_available=True)
    
    if product.vendor.is_on_vacation:
        messages.error(request, f'Cannot add {product.name} to cart - vendor is on vacation.')
        return redirect('products:detail', pk=product_id)
    
    cart, created = Cart.objects.get_or_create(user=request.user)
    
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 1}
    )
    
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    
    messages.success(request, f'{product.name} added to cart!')
    return redirect('products:detail', pk=product_id)


@login_required
def order_list(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'orders/list.html', {'orders': orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, 'orders/detail.html', {'order': order})
