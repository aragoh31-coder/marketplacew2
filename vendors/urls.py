from django.urls import path
from . import views

app_name = 'vendors'

urlpatterns = [
    path('', views.vendor_list, name='list'),
    path('<uuid:pk>/', views.vendor_detail, name='detail'),
    path('profile/<uuid:vendor_id>/', views.vendor_profile, name='profile'),
    path('dashboard/', views.vendor_dashboard, name='dashboard'),
    path('apply/', views.vendor_apply, name='apply'),
    
    path('products/', views.vendor_products, name='products'),
    path('products/create/', views.create_product, name='create_product'),
    path('products/<uuid:product_id>/edit/', views.edit_product, name='edit_product'),
    path('products/<uuid:product_id>/delete/', views.delete_product, name='delete_product'),
    path('products/<uuid:product_id>/toggle/', views.toggle_product, name='toggle_product'),
    
    path('orders/', views.vendor_orders, name='orders'),
    path('orders/<uuid:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<uuid:order_id>/ship/', views.ship_order, name='ship_order'),
    path('orders/<uuid:order_id>/cancel/', views.cancel_order, name='cancel_order'),
    
    path('settings/', views.vendor_settings, name='settings'),
    path('vacation/', views.vacation_mode, name='vacation_mode'),
    path('vacation/settings/', views.vacation_settings, name='vacation_settings'),
    path('subvendors/', views.manage_subvendors, name='manage_subvendors'),
    path('subvendors/create/', views.create_subvendor, name='create_subvendor'),
    path('subvendors/<uuid:subvendor_id>/edit/', views.edit_subvendor, name='edit_subvendor'),
    path('subvendors/<uuid:subvendor_id>/deactivate/', views.deactivate_subvendor, name='deactivate_subvendor'),
    path('subvendors/<uuid:subvendor_id>/activity/', views.subvendor_activity_log, name='subvendor_activity_log'),
    path('stats/', views.vendor_stats, name='vendor_stats'),
]
