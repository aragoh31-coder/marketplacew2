from django.urls import path
from .views import (
    admin_login, admin_logout, secondary_auth, pgp_verify, locked_account,
    admin_dashboard, admin_users, admin_user_detail, admin_user_action,
    vendors_list, approve_vendor,
    products_list, delete_product,
    orders_list,
    disputes_list, resolve_dispute,
    withdrawals_list, approve_withdrawal,
    system_logs, trigger_maintenance, image_settings,
    admin_withdrawal_detail, admin_security_logs, admin_wallet_overview,
    withdrawal_management, withdrawal_detail, withdrawal_approve, 
    withdrawal_reject, withdrawal_add_notes
)

app_name = 'adminpanel'
urlpatterns = [
    path('login/', admin_login, name='login'),
    path('logout/', admin_logout, name='logout'),
    path('secondary-auth/', secondary_auth, name='secondary_auth'),
    path('pgp-verify/', pgp_verify, name='pgp_verify'),
    path('locked/', locked_account, name='locked'),
    
    path('', admin_dashboard, name='dashboard'),
    path('dashboard/', admin_dashboard, name='dashboard'),
    path('users/', admin_users, name='users'),
    path('user/<str:username>/', admin_user_detail, name='user_detail'),
    path('user/<str:username>/action/', admin_user_action, name='user_action'),
    
    path('vendors/', vendors_list, name='vendors'),
    path('approve_vendor/<uuid:vendor_id>/', approve_vendor, name='approve_vendor'),
    path('products/', products_list, name='products'),
    path('delete_product/<uuid:product_id>/', delete_product, name='delete_product'),
    path('orders/', orders_list, name='orders'),
    path('disputes/', disputes_list, name='disputes'),
    path('resolve_dispute/<uuid:dispute_id>/', resolve_dispute, name='resolve_dispute'),
    path('withdrawals/', withdrawals_list, name='withdrawals'),
    path('approve_withdrawal/<uuid:withdrawal_id>/', approve_withdrawal, name='approve_withdrawal'),
    path('logs/', system_logs, name='logs'),
    path('maintenance/', trigger_maintenance, name='maintenance'),
    path('image-settings/', image_settings, name='image_settings'),
    path('withdrawal/<int:withdrawal_id>/', admin_withdrawal_detail, name='withdrawal_detail'),
    path('security-logs/', admin_security_logs, name='security_logs'),
    path('wallet-overview/', admin_wallet_overview, name='wallet_overview'),
    
    path('withdrawal-management/', withdrawal_management, name='withdrawal_management'),
    path('withdrawal-detail/<int:withdrawal_id>/', withdrawal_detail, name='withdrawal_detail'),
    path('withdrawal-approve/<int:withdrawal_id>/', withdrawal_approve, name='withdrawal_approve'),
    path('withdrawal-reject/<int:withdrawal_id>/', withdrawal_reject, name='withdrawal_reject'),
    path('withdrawal-notes/<int:withdrawal_id>/', withdrawal_add_notes, name='withdrawal_add_notes'),
]
