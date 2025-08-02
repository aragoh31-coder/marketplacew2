from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count, Q, Avg, F
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.core.paginator import Paginator
from django.core.cache import cache
from django_ratelimit.decorators import ratelimit

from .models import Vendor, SubVendor, SubVendorActivityLog
from .forms import VendorApplicationForm, ProductForm, VendorSettingsForm, VacationModeForm, SubVendorForm


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
from products.models import Product
from orders.models import Order, OrderItem
from adminpanel.utils import ChartGenerator
from django.contrib.auth import get_user_model

User = get_user_model()


@ratelimit(key='ip', rate='10/m', method='GET')
def vendor_list(request):
    vendors = Vendor.objects.filter(
        is_active=True,
        user__is_active=True
    ).order_by('-trust_level')
    
    search = request.GET.get('q')
    if search:
        vendors = vendors.filter(
            Q(user__username__icontains=search) |
            Q(description__icontains=search)
        )
    
    paginator = Paginator(vendors, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'vendors/list.html', {'page_obj': page_obj})


@ratelimit(key='ip', rate='20/m', method='GET')
def vendor_detail(request, pk):
    vendor = get_object_or_404(Vendor, pk=pk, is_approved=True, is_active=True)
    return render(request, 'vendors/detail.html', {'vendor': vendor})


@login_required
@ratelimit(key='user', rate='30/m', method='GET')
def vendor_dashboard(request):
    try:
        subvendor = SubVendor.objects.get(user=request.user, is_active=True)
        return subvendor_dashboard(request, subvendor)
    except SubVendor.DoesNotExist:
        pass
    
    if not hasattr(request.user, 'vendor'):
        messages.error(request, 'You are not registered as a vendor.')
        return redirect('vendors:apply')
    
    vendor = request.user.vendor
    
    if vendor.is_on_vacation:
        messages.warning(request, 'Your store is in vacation mode. Products are visible but marked as "On Vacation Listing" and cannot be purchased.')
    
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    vendor_orders = Order.objects.filter(
        items__product__vendor=vendor
    ).distinct()
    
    total_sales = vendor_orders.filter(
        status='completed'
    ).count()
    
    week_sales = vendor_orders.filter(
        status='completed',
        created_at__date__gte=week_ago
    ).count()
    
    revenue_stats = vendor_orders.filter(
        status='completed'
    ).aggregate(
        total_btc=Sum('total_btc'),
        total_xmr=Sum('total_xmr')
    )
    
    total_revenue_btc = revenue_stats['total_btc'] or Decimal('0')
    total_revenue_xmr = revenue_stats['total_xmr'] or Decimal('0')
    
    week_revenue = vendor_orders.filter(
        status='completed',
        created_at__date__gte=week_ago
    ).aggregate(
        btc=Sum('total_btc'),
        xmr=Sum('total_xmr')
    )
    
    pending_orders = vendor_orders.filter(
        status__in=['paid', 'created']
    ).count()
    
    active_products = Product.objects.filter(
        vendor=vendor,
        is_active=True
    ).count()
    
    recent_orders = vendor_orders.order_by('-created_at')[:10]
    
    low_stock = Product.objects.filter(
        vendor=vendor,
        is_active=True,
        stock_quantity__lte=5
    ).order_by('stock_quantity')
    
    escrow_stats = vendor_orders.filter(
        status='shipped'
    ).aggregate(
        escrow_btc=Sum('total_btc'),
        escrow_xmr=Sum('total_xmr')
    )
    
    context = {
        'vendor': vendor,
        'total_sales': total_sales,
        'week_sales': week_sales,
        'total_revenue_btc': total_revenue_btc,
        'total_revenue_xmr': total_revenue_xmr,
        'week_revenue_btc': week_revenue['btc'] or Decimal('0'),
        'week_revenue_xmr': week_revenue['xmr'] or Decimal('0'),
        'pending_orders': pending_orders,
        'active_products': active_products,
        'recent_orders': recent_orders,
        'low_stock': low_stock,
        'escrow_btc': escrow_stats['escrow_btc'] or Decimal('0'),
        'escrow_xmr': escrow_stats['escrow_xmr'] or Decimal('0'),
    }
    
    return render(request, 'vendors/dashboard.html', context)


def subvendor_dashboard(request, subvendor):
    """Dashboard for sub-vendor accounts"""
    vendor = subvendor.main_vendor
    
    subvendor.last_login = timezone.now()
    subvendor.save()
    
    context = {
        'is_subvendor': True,
        'subvendor': subvendor,
        'vendor': vendor,
        'permissions': {
            'view_orders': subvendor.can_view_orders,
            'respond_messages': subvendor.can_respond_messages,
            'update_tracking': subvendor.can_update_tracking,
            'process_refunds': subvendor.can_process_refunds,
        },
        'message_limit': subvendor.daily_message_limit,
        'messages_sent_today': subvendor.messages_sent_today,
    }
    
    if subvendor.can_view_orders:
        vendor_orders = Order.objects.filter(
            items__product__vendor=vendor
        ).distinct()
        
        context['pending_orders'] = vendor_orders.filter(
            status__in=['paid', 'created']
        ).count()
        context['recent_orders'] = vendor_orders.order_by('-created_at')[:10]
    
    return render(request, 'vendors/subvendor_dashboard.html', context)


@login_required
def vendor_products(request):
    if not hasattr(request.user, 'vendor'):
        return redirect('vendors:apply')
    
    vendor = request.user.vendor
    products = Product.objects.filter(vendor=vendor).order_by('-created_at')
    
    category = request.GET.get('category')
    status = request.GET.get('status')
    search = request.GET.get('q')
    
    if category:
        products = products.filter(category=category)
    
    if status == 'active':
        products = products.filter(is_active=True)
    elif status == 'inactive':
        products = products.filter(is_active=False)
    
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search)
        )
    
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'vendors/products.html', {
        'page_obj': page_obj,
        'vendor': vendor,
    })

@login_required
def create_product(request):
    if not hasattr(request.user, 'vendor'):
        return redirect('vendors:apply')
    
    vendor = request.user.vendor
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False, user=request.user)
            if product:  # Check if form processing succeeded
                product.vendor = vendor
                product.save()
                messages.success(request, 'Product created successfully!')
                return redirect('vendors:products')
    else:
        form = ProductForm()
    
    return render(request, 'vendors/create_product.html', {
        'form': form,
        'vendor': vendor,
    })

@login_required
def edit_product(request, product_id):
    if not hasattr(request.user, 'vendor'):
        return redirect('vendors:apply')
    
    vendor = request.user.vendor
    product = get_object_or_404(Product, id=product_id, vendor=vendor)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            updated_product = form.save(user=request.user)
            if updated_product:  # Check if form processing succeeded
                messages.success(request, 'Product updated successfully!')
                return redirect('vendors:products')
    else:
        form = ProductForm(instance=product)
    
    return render(request, 'vendors/edit_product.html', {
        'form': form,
        'product': product,
        'vendor': vendor,
    })

@login_required
def delete_product(request, product_id):
    if not hasattr(request.user, 'vendor'):
        return redirect('vendors:apply')
    
    vendor = request.user.vendor
    product = get_object_or_404(Product, id=product_id, vendor=vendor)
    
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted successfully!')
        return redirect('vendors:products')
    
    return render(request, 'vendors/delete_product.html', {
        'product': product,
        'vendor': vendor,
    })

@login_required
def toggle_product(request, product_id):
    if not hasattr(request.user, 'vendor'):
        return redirect('vendors:apply')
    
    vendor = request.user.vendor
    product = get_object_or_404(Product, id=product_id, vendor=vendor)
    
    product.is_active = not product.is_active
    product.save()
    
    status = 'activated' if product.is_active else 'deactivated'
    messages.success(request, f'Product {status} successfully!')
    
    return redirect('vendors:products')

@login_required
def vendor_orders(request):
    if not hasattr(request.user, 'vendor'):
        return redirect('vendors:apply')
    
    vendor = request.user.vendor
    
    orders = Order.objects.filter(
        items__product__vendor=vendor
    ).distinct().order_by('-created_at')
    
    status = request.GET.get('status')
    if status:
        orders = orders.filter(status=status)
    
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'vendors/orders.html', {
        'page_obj': page_obj,
        'vendor': vendor,
    })

@login_required
def order_detail(request, order_id):
    if not hasattr(request.user, 'vendor'):
        return redirect('vendors:apply')
    
    vendor = request.user.vendor
    order = get_object_or_404(Order, id=order_id)
    
    vendor_items = order.items.filter(product__vendor=vendor)
    
    if not vendor_items.exists():
        messages.error(request, 'You do not have access to this order.')
        return redirect('vendors:orders')
    
    return render(request, 'vendors/order_detail.html', {
        'order': order,
        'vendor_items': vendor_items,
        'vendor': vendor,
    })

@login_required
def ship_order(request, order_id):
    if not hasattr(request.user, 'vendor'):
        return redirect('vendors:apply')
    
    vendor = request.user.vendor
    order = get_object_or_404(Order, id=order_id)
    
    if not order.items.filter(product__vendor=vendor).exists():
        messages.error(request, 'You do not have access to this order.')
        return redirect('vendors:orders')
    
    if request.method == 'POST':
        with transaction.atomic():
            order.status = 'shipped'
            order.shipped_at = timezone.now()
            order.save()
            
            messages.success(request, 'Order marked as shipped!')
    
    return redirect('vendors:order_detail', order_id=order.id)

@login_required
def cancel_order(request, order_id):
    if not hasattr(request.user, 'vendor'):
        return redirect('vendors:apply')
    
    vendor = request.user.vendor
    order = get_object_or_404(Order, id=order_id)
    
    if not order.items.filter(product__vendor=vendor).exists():
        messages.error(request, 'You do not have access to this order.')
        return redirect('vendors:orders')
    
    if order.status in ['created', 'paid']:
        with transaction.atomic():
            order.status = 'cancelled'
            order.save()
            
            for item in order.items.filter(product__vendor=vendor):
                item.product.stock_quantity += item.quantity
                item.product.save()
            
            messages.success(request, 'Order cancelled successfully!')
    else:
        messages.error(request, 'Cannot cancel order in current status.')
    
    return redirect('vendors:orders')

@login_required
def vendor_settings(request):
    if not hasattr(request.user, 'vendor'):
        return redirect('vendors:apply')
    
    vendor = request.user.vendor
    
    if request.method == 'POST':
        form = VendorSettingsForm(request.POST, instance=vendor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings updated successfully!')
            return redirect('vendors:dashboard')
    else:
        form = VendorSettingsForm(instance=vendor)
    
    return render(request, 'vendors/settings.html', {
        'form': form,
        'vendor': vendor,
    })

@login_required
def vendor_apply(request):
    if hasattr(request.user, 'vendor'):
        messages.info(request, 'You are already a vendor.')
        return redirect('vendors:dashboard')
    
    if request.method == 'POST':
        form = VendorApplicationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                vendor = form.save(commit=False)
                vendor.user = request.user
                vendor.save()
                
                request.user.is_vendor = True
                request.user.save()
                
                messages.success(request, 'Vendor application submitted! Your account is now active.')
                return redirect('vendors:dashboard')
    else:
        form = VendorApplicationForm()
    
    return render(request, 'vendors/apply.html', {'form': form})


def vendor_profile(request, vendor_id):
    vendor = get_object_or_404(Vendor, id=vendor_id, is_active=True)
    
    products = Product.objects.filter(
        vendor=vendor,
        is_active=True
    ).order_by('-created_at')
    
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    total_sales = Order.objects.filter(
        items__product__vendor=vendor,
        status='completed'
    ).distinct().count()
    
    return render(request, 'vendors/profile.html', {
        'vendor': vendor,
        'page_obj': page_obj,
        'total_sales': total_sales,
    })


@login_required
def vacation_settings(request):
    """Manage vacation mode settings"""
    if not hasattr(request.user, 'vendor'):
        messages.error(request, 'You are not registered as a vendor.')
        return redirect('vendors:apply')
    
    vendor = request.user.vendor
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'activate':
            form = VacationModeForm(request.POST)
            if form.is_valid():
                vendor.activate_vacation_mode(
                    message=form.cleaned_data.get('vacation_message', ''),
                    ends_at=form.cleaned_data.get('vacation_ends')
                )
                messages.success(request, 'Vacation mode activated. Products will show "On Vacation Listing" status.')
                return redirect('vendors:vacation_settings')
        
        elif action == 'deactivate':
            vendor.deactivate_vacation_mode()
            messages.success(request, 'Vacation mode deactivated. Products are available for purchase again.')
            return redirect('vendors:vacation_settings')
    
    form = VacationModeForm(initial={
        'vacation_message': vendor.vacation_message,
        'vacation_ends': vendor.vacation_ends
    })
    
    return render(request, 'vendors/vacation_settings.html', {
        'form': form,
        'vendor': vendor,
    })


@login_required
def manage_subvendors(request):
    """Manage sub-vendor accounts"""
    if not hasattr(request.user, 'vendor'):
        messages.error(request, 'You are not registered as a vendor.')
        return redirect('vendors:apply')
    
    vendor = request.user.vendor
    subvendors = vendor.sub_vendors.all().order_by('-created_at')
    
    return render(request, 'vendors/manage_subvendors.html', {
        'vendor': vendor,
        'subvendors': subvendors,
        'can_create_more': subvendors.count() < 2,
    })


@login_required
def create_subvendor(request):
    """Create a new sub-vendor account"""
    if not hasattr(request.user, 'vendor'):
        messages.error(request, 'You are not registered as a vendor.')
        return redirect('vendors:apply')
    
    vendor = request.user.vendor
    
    if vendor.sub_vendors.count() >= 2:
        messages.error(request, 'You can only create up to 2 sub-vendor accounts.')
        return redirect('vendors:manage_subvendors')
    
    if request.method == 'POST':
        form = SubVendorForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            full_username = f"{vendor.vendor_name.lower()}_{username}"
            
            if User.objects.filter(username=full_username).exists():
                messages.error(request, 'This sub-vendor username already exists.')
                return render(request, 'vendors/create_subvendor.html', {'form': form})
            
            sub_user = User.objects.create_user(
                username=full_username,
                password=password,
                email=f"{full_username}@subvendor.local"
            )
            
            sub_vendor = SubVendor.objects.create(
                main_vendor=vendor,
                user=sub_user,
                created_by=request.user,
                can_view_orders=form.cleaned_data['can_view_orders'],
                can_respond_messages=form.cleaned_data['can_respond_messages'],
                can_update_tracking=form.cleaned_data['can_update_tracking'],
                can_process_refunds=form.cleaned_data['can_process_refunds'],
                daily_message_limit=form.cleaned_data['daily_message_limit'],
            )
            
            SubVendorActivityLog.objects.create(
                sub_vendor=sub_vendor,
                action='account_created',
                details={
                    'created_by': request.user.username,
                    'permissions': {
                        'view_orders': sub_vendor.can_view_orders,
                        'respond_messages': sub_vendor.can_respond_messages,
                        'update_tracking': sub_vendor.can_update_tracking,
                        'process_refunds': sub_vendor.can_process_refunds,
                    }
                }
            )
            
            messages.success(request, f'Sub-vendor account created: {username}')
            return redirect('vendors:manage_subvendors')
    else:
        form = SubVendorForm()
    
    return render(request, 'vendors/create_subvendor.html', {
        'form': form,
        'vendor': vendor,
    })


@login_required
def edit_subvendor(request, subvendor_id):
    """Edit sub-vendor permissions"""
    vendor = get_object_or_404(Vendor, user=request.user)
    subvendor = get_object_or_404(SubVendor, id=subvendor_id, main_vendor=vendor)
    
    if request.method == 'POST':
        form = SubVendorForm(request.POST, instance=subvendor, editing=True)
        if form.is_valid():
            old_permissions = {
                'view_orders': subvendor.can_view_orders,
                'respond_messages': subvendor.can_respond_messages,
                'update_tracking': subvendor.can_update_tracking,
                'process_refunds': subvendor.can_process_refunds,
            }
            
            form.save()
            
            new_permissions = {
                'view_orders': subvendor.can_view_orders,
                'respond_messages': subvendor.can_respond_messages,
                'update_tracking': subvendor.can_update_tracking,
                'process_refunds': subvendor.can_process_refunds,
            }
            
            SubVendorActivityLog.objects.create(
                sub_vendor=subvendor,
                action='permissions_updated',
                details={
                    'updated_by': request.user.username,
                    'old_permissions': old_permissions,
                    'new_permissions': new_permissions,
                }
            )
            
            messages.success(request, 'Sub-vendor permissions updated.')
            return redirect('vendors:manage_subvendors')
    else:
        form = SubVendorForm(instance=subvendor, editing=True)
    
    return render(request, 'vendors/edit_subvendor.html', {
        'form': form,
        'subvendor': subvendor,
        'vendor': vendor,
    })


@login_required
def deactivate_subvendor(request, subvendor_id):
    """Deactivate a sub-vendor account"""
    vendor = get_object_or_404(Vendor, user=request.user)
    subvendor = get_object_or_404(SubVendor, id=subvendor_id, main_vendor=vendor)
    
    if request.method == 'POST':
        subvendor.is_active = False
        subvendor.deactivated_at = timezone.now()
        subvendor.save()
        
        subvendor.user.is_active = False
        subvendor.user.save()
        
        SubVendorActivityLog.objects.create(
            sub_vendor=subvendor,
            action='account_deactivated',
            details={
                'deactivated_by': request.user.username,
            }
        )
        
        messages.success(request, f'Sub-vendor account {subvendor.user.username} has been deactivated.')
        return redirect('vendors:manage_subvendors')
    
    return render(request, 'vendors/deactivate_subvendor.html', {
        'subvendor': subvendor,
        'vendor': vendor,
    })


@login_required
@ratelimit(key='user', rate='30/m', method='GET')
def subvendor_activity_log(request, subvendor_id):
    """View sub-vendor activity log"""
    vendor = get_object_or_404(Vendor, user=request.user)
    subvendor = get_object_or_404(SubVendor, id=subvendor_id, main_vendor=vendor)
    
    activities = subvendor.activity_logs.all()[:100]
    
    return render(request, 'vendors/subvendor_activity_log.html', {
        'subvendor': subvendor,
        'activities': activities,
        'vendor': vendor,
    })


@login_required
def vacation_mode(request):
    """Legacy vacation mode toggle - redirect to new settings"""
    return redirect('vendors:vacation_settings')


@login_required
def vendor_stats(request):
    """Display comprehensive vendor statistics"""
    vendors = Vendor.objects.filter(is_approved=True, is_active=True).annotate(
        total_orders=Count('products__orderitem__order', distinct=True),
        total_revenue_btc=Sum('products__orderitem__order__total_btc'),
        total_revenue_xmr=Sum('products__orderitem__order__total_xmr'),
        avg_rating=Avg('feedback__rating')
    ).order_by('-total_orders')
    
    total_vendors = vendors.count()
    total_bonded_vendors = vendors.filter(bond_paid=True).count()
    total_revenue_btc = vendors.aggregate(Sum('total_revenue_btc'))['total_revenue_btc__sum'] or 0
    total_revenue_xmr = vendors.aggregate(Sum('total_revenue_xmr'))['total_revenue_xmr__sum'] or 0
    
    context = {
        'vendors': vendors[:20],
        'total_vendors': total_vendors,
        'total_bonded_vendors': total_bonded_vendors,
        'total_revenue_btc': total_revenue_btc,
        'total_revenue_xmr': total_revenue_xmr,
    }
    
    return render(request, 'vendors/stats.html', context)
