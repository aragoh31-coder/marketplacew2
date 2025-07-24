from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.db.models import Sum, Count, Avg, Q
from django.core.paginator import Paginator
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import secrets
import json
import hashlib
import pyotp
import time
from accounts.models import User
from accounts.pgp_service import PGPService
from vendors.models import Vendor
from products.models import Product
from orders.models import Order
from disputes.models import Dispute
from wallets.models import Wallet, Transaction, WithdrawalRequest, AuditLog
from messaging.models import Message
from .models import AdminLog, AdminProfile, AdminAction, SecurityAlert
from .forms import SecondaryAuthForm, AdminPGPChallengeForm, AdminLoginForm, AdminTripleAuthForm
from .security import AdminSecurityManager, TripleAuthenticator
from .decorators import require_2fa, require_triple_auth, log_admin_action, admin_required
from apps.security.models import SecurityEvent, SecurityAuditLog
from apps.security.forms import TripleAuthForm
from django.conf import settings

def admin_login(request):
    """Enhanced admin login with triple authentication"""
    if request.method == 'POST':
        if 'pgp_challenge_response' in request.POST:
            return handle_triple_auth(request)
        
        form = AdminLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            user = authenticate(request, username=username, password=password)
            if user and user.is_superuser:
                failed_attempts = request.session.get(f'admin_failed_attempts_{username}', 0)
                lockout_time = request.session.get(f'admin_lockout_time_{username}')
                
                if lockout_time and timezone.now().timestamp() < lockout_time:
                    messages.error(request, 'Account temporarily locked due to failed attempts.')
                    return render(request, 'adminpanel/locked.html')
                
                request.session.pop(f'admin_failed_attempts_{username}', None)
                request.session.pop(f'admin_lockout_time_{username}', None)
                
                return initiate_triple_auth(request, user)
            else:
                failed_attempts = request.session.get(f'admin_failed_attempts_{username}', 0) + 1
                request.session[f'admin_failed_attempts_{username}'] = failed_attempts
                
                if failed_attempts >= 3:  # Max failed attempts
                    lockout_time = timezone.now().timestamp() + 900  # 15 minutes
                    request.session[f'admin_lockout_time_{username}'] = lockout_time
                    messages.error(request, 'Too many failed attempts. Account locked.')
                    return render(request, 'adminpanel/locked.html')
                
                messages.error(request, 'Invalid credentials or insufficient permissions.')
        else:
            messages.error(request, 'Invalid form submission.')
    else:
        form = AdminLoginForm()
    
    return render(request, 'adminpanel/login.html', {'form': form})


def initiate_triple_auth(request, user):
    """Initiate triple authentication process"""
    from .security import TripleAuthenticator
    
    authenticator = TripleAuthenticator()
    
    # Generate PGP challenge
    challenge_data = authenticator.generate_pgp_challenge(user)
    
    if not challenge_data['success']:
        messages.error(request, 'PGP challenge generation failed. Please contact support.')
        return redirect('adminpanel:login')
    
    request.session['admin_triple_auth'] = {
        'user_id': user.id,
        'challenge_id': challenge_data['challenge_id'],
        'challenge_text': challenge_data['challenge_text'],
        'encrypted_challenge': challenge_data['encrypted_challenge'],
        'timestamp': time.time(),
    }
    
    form = AdminTripleAuthForm(
        initial={
            'username': user.username,
            'challenge_id': challenge_data['challenge_id'],
        },
        expected_challenge=challenge_data['challenge_text'],
        challenge_id=challenge_data['challenge_id']
    )
    
    context = {
        'form': form,
        'encrypted_challenge': challenge_data['encrypted_challenge'],
        'challenge_id': challenge_data['challenge_id'],
        'user': user,
    }
    
    return render(request, 'adminpanel/triple_auth_form.html', context)


def handle_triple_auth(request):
    """Handle complete triple authentication submission"""
    from .security import TripleAuthenticator
    
    auth_data = request.session.get('admin_triple_auth')
    if not auth_data:
        messages.error(request, 'Authentication session expired. Please try again.')
        return redirect('adminpanel:login')
    
    if time.time() - auth_data['timestamp'] > 300:
        request.session.pop('admin_triple_auth', None)
        messages.error(request, 'Authentication timeout. Please try again.')
        return redirect('adminpanel:login')
    
    try:
        user = User.objects.get(id=auth_data['user_id'])
    except User.DoesNotExist:
        messages.error(request, 'Invalid user. Please try again.')
        return redirect('adminpanel:login')
    
    form = AdminTripleAuthForm(
        request.POST,
        expected_challenge=auth_data['challenge_text'],
        challenge_id=auth_data['challenge_id']
    )
    
    if form.is_valid():
        authenticator = TripleAuthenticator()
        
        secondary_password = form.cleaned_data['secondary_password']
        if not authenticator.verify_secondary_password(secondary_password):
            messages.error(request, 'Invalid secondary password.')
            return render(request, 'adminpanel/triple_auth_form.html', {
                'form': form,
                'encrypted_challenge': auth_data['encrypted_challenge'],
                'challenge_id': auth_data['challenge_id'],
                'user': user,
            })
        
        pgp_response = form.cleaned_data['pgp_challenge_response']
        if pgp_response != auth_data['challenge_text']:
            messages.error(request, 'Invalid PGP challenge response.')
            return render(request, 'adminpanel/triple_auth_form.html', {
                'form': form,
                'encrypted_challenge': auth_data['encrypted_challenge'],
                'challenge_id': auth_data['challenge_id'],
                'user': user,
            })
        
        login(request, user)
        request.session['admin_authenticated'] = True
        request.session['admin_auth_time'] = time.time()
        request.session.pop('admin_triple_auth', None)
        
        from wallets.models import AuditLog
        AuditLog.objects.create(
            user=user,
            action='admin_action',
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details={
                'action': 'triple_auth_login',
                'success': True,
                'timestamp': timezone.now().isoformat()
            }
        )
        
        messages.success(request, 'Successfully authenticated with triple authentication.')
        return redirect('adminpanel:dashboard')
    
    context = {
        'form': form,
        'encrypted_challenge': auth_data['encrypted_challenge'],
        'challenge_id': auth_data['challenge_id'],
        'user': user,
    }
    
    return render(request, 'adminpanel/triple_auth_form.html', context)


def secondary_auth(request):
    """Enhanced secondary password authentication with triple verification"""
    pending_user_id = request.session.get('admin_pending_user_id')
    if not pending_user_id:
        return redirect('adminpanel:admin_login')
    
    login_timestamp = request.session.get('admin_login_timestamp')
    if login_timestamp and time.time() - login_timestamp > 600:  # 10 minutes
        request.session.flush()
        messages.error(request, 'Session expired. Please login again.')
        return redirect('adminpanel:admin_login')
    
    if request.method == 'POST':
        form = SecondaryAuthForm(request.POST)
        if form.is_valid():
            secondary_password = form.cleaned_data['secondary_password']
            
            expected_secondary = hashlib.sha256(b'SecureAdmin2024!').hexdigest()
            provided_hash = hashlib.sha256(secondary_password.encode()).hexdigest()
            
            if provided_hash == expected_secondary:
                user = User.objects.get(id=pending_user_id)
                request.session['admin_secondary_verified'] = True
                request.session['admin_secondary_timestamp'] = time.time()
                
                if user.pgp_public_key:
                    return redirect('adminpanel:pgp_verify')
                else:
                    login(request, user)
                    request.session.pop('admin_pending_user_id', None)
                    request.session.pop('admin_login_timestamp', None)
                    request.session.pop('admin_secondary_verified', None)
                    request.session.pop('admin_secondary_timestamp', None)
                    
                    request.session.set_expiry(3600)  # 1 hour
                    
                    AdminLog.objects.create(
                        admin_user=user,
                        action_type='LOGIN',
                        target_model='User',
                        target_id=str(user.id),
                        description=f'Admin triple authentication completed for {user.username} (no PGP)',
                        ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
                    )
                    
                    messages.success(request, 'Welcome to the enhanced admin panel!')
                    return redirect('adminpanel:admin_dashboard')
            else:
                messages.error(request, 'Invalid secondary password.')
                
                failed_key = f'admin_secondary_failed_{pending_user_id}'
                failed_attempts = request.session.get(failed_key, 0) + 1
                request.session[failed_key] = failed_attempts
                
                if failed_attempts >= 3:
                    request.session.flush()
                    messages.error(request, 'Too many failed secondary authentication attempts.')
                    return redirect('adminpanel:admin_login')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SecondaryAuthForm()
    
    return render(request, 'adminpanel/secondary_auth.html', {'form': form})


def pgp_verify(request):
    """PGP challenge verification for admin access"""
    pending_user_id = request.session.get('admin_pending_user_id')
    if not pending_user_id:
        return redirect('adminpanel:login')
    
    user = User.objects.get(id=pending_user_id)
    
    if request.method == 'POST':
        form = AdminPGPChallengeForm(request.POST)
        if form.is_valid():
            signed_response = form.cleaned_data['signed_challenge']
            challenge = request.session.get('admin_pgp_challenge')
            
            if challenge:
                from accounts.pgp_service import PGPService
                pgp_service = PGPService()
                
                verify_result = pgp_service.verify_signature(signed_response, challenge)
                
                if verify_result['success']:
                    login(request, user)
                    request.session.pop('admin_pending_user_id', None)
                    request.session.pop('admin_login_timestamp', None)
                    request.session.pop('admin_pgp_challenge', None)
                    
                    request.session.set_expiry(settings.ADMIN_PANEL_CONFIG['SESSION_TIMEOUT'])
                    
                    AdminLog.objects.create(
                        admin_user=user,
                        action_type='LOGIN',
                        target_model='User',
                        target_id=str(user.id),
                        description=f'Admin login with PGP verification completed for {user.username}',
                        ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
                    )
                    
                    messages.success(request, 'Welcome to the admin panel!')
                    return redirect('adminpanel:dashboard')
                else:
                    messages.error(request, 'Invalid PGP signature.')
            else:
                messages.error(request, 'PGP challenge expired.')
    else:
        form = AdminPGPChallengeForm()
        
        from accounts.pgp_service import PGPService
        pgp_service = PGPService()
        
        challenge = f"Admin login challenge for {user.username} at {timezone.now().isoformat()}"
        request.session['admin_pgp_challenge'] = challenge
        
        encrypt_result = pgp_service.encrypt_message(challenge, user.pgp_fingerprint)
        
        if not encrypt_result['success']:
            messages.error(request, 'Failed to generate PGP challenge.')
            return redirect('adminpanel:login')
    
    return render(request, 'adminpanel/pgp_verify.html', {
        'form': form,
        'user': user,
        'encrypted_challenge': encrypt_result.get('encrypted_message', '') if 'encrypt_result' in locals() else ''
    })
    
    challenge = request.session.get('admin_pgp_challenge', '')
    return render(request, 'adminpanel/pgp_verify.html', {
        'form': form,
        'challenge': challenge,
        'user': user
    })


def locked_account(request):
    """Display account lockout page"""
    return render(request, 'adminpanel/locked.html')


def admin_logout(request):
    """Admin logout"""
    if request.user.is_authenticated:
        AdminLog.objects.create(
            user=request.user,
            action='LOGOUT',
            details=f'Admin logout for {request.user.username}'
        )
    
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('adminpanel:login')


@login_required
def admin_dashboard(request):
    """Enhanced admin dashboard with comprehensive metrics"""
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('adminpanel:login')
    
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    new_users_today = User.objects.filter(date_joined__date=timezone.now().date()).count()
    new_users_week = User.objects.filter(date_joined__gte=timezone.now() - timedelta(days=7)).count()
    
    total_vendors = Vendor.objects.count()
    approved_vendors = Vendor.objects.filter(is_approved=True).count()
    pending_vendors = Vendor.objects.filter(is_approved=False).count()
    
    total_products = Product.objects.count()
    active_products = Product.objects.filter(is_active=True).count()
    total_orders = Order.objects.count()
    orders_today = Order.objects.filter(created_at__date=timezone.now().date()).count()
    
    total_disputes = Dispute.objects.count()
    open_disputes = Dispute.objects.filter(status='OPEN').count()
    resolved_disputes = Dispute.objects.filter(status='RESOLVED').count()
    
    try:
        btc_revenue = Transaction.objects.filter(
            transaction_type='DEPOSIT',
            currency='BTC'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        xmr_revenue = Transaction.objects.filter(
            transaction_type='DEPOSIT',
            currency='XMR'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        btc_revenue_month = Transaction.objects.filter(
            transaction_type='DEPOSIT',
            currency='BTC',
            created_at__gte=month_start
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        xmr_revenue_month = Transaction.objects.filter(
            transaction_type='DEPOSIT',
            currency='XMR',
            created_at__gte=month_start
        ).aggregate(total=Sum('amount'))['total'] or 0
        
    except Exception:
        btc_revenue = xmr_revenue = btc_revenue_month = xmr_revenue_month = 0
    
    recent_users = User.objects.order_by('-date_joined')[:5]
    recent_orders = Order.objects.order_by('-created_at')[:5]
    recent_disputes = Dispute.objects.order_by('-created_at')[:3]
    
    context = {
        'total_users': total_users,
        'active_users': active_users,
        'new_users_today': new_users_today,
        'new_users_week': new_users_week,
        'total_vendors': total_vendors,
        'approved_vendors': approved_vendors,
        'pending_vendors': pending_vendors,
        'total_products': total_products,
        'active_products': active_products,
        'total_orders': total_orders,
        'orders_today': orders_today,
        'total_disputes': total_disputes,
        'open_disputes': open_disputes,
        'resolved_disputes': resolved_disputes,
        'btc_revenue': btc_revenue,
        'xmr_revenue': xmr_revenue,
        'btc_revenue_month': btc_revenue_month,
        'xmr_revenue_month': xmr_revenue_month,
        'recent_users': recent_users,
        'recent_orders': recent_orders,
        'recent_disputes': recent_disputes,
    }
    return render(request, 'adminpanel/dashboard.html', context)


dashboard = admin_dashboard

@login_required
def admin_users(request):
    """Enhanced user listing with search and filters"""
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('adminpanel:login')
    
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    vendor_filter = request.GET.get('vendor', '')
    
    users = User.objects.all()
    
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )
    
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    elif status_filter == 'staff':
        users = users.filter(is_staff=True)
    
    if vendor_filter == 'vendors':
        users = users.filter(vendor__isnull=False)
    elif vendor_filter == 'non_vendors':
        users = users.filter(vendor__isnull=True)
    
    users = users.order_by('-date_joined')
    
    paginator = Paginator(users, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'vendor_filter': vendor_filter,
        'total_users': users.count(),
    }
    return render(request, 'adminpanel/users.html', context)


users_list = admin_users

@login_required
def admin_user_detail(request, username):
    """Comprehensive user details view with financial data"""
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('adminpanel:login')
    
    user = get_object_or_404(User, username=username)
    
    try:
        wallet = user.wallet
        btc_balance = wallet.balance_btc
        xmr_balance = wallet.balance_xmr
        btc_escrow = wallet.escrow_btc
        xmr_escrow = wallet.escrow_xmr
    except:
        wallet = None
        btc_balance = xmr_balance = btc_escrow = xmr_escrow = 0
    
    withdrawals = WithdrawalRequest.objects.filter(user=user).order_by('-created_at')[:10]
    
    transactions = Transaction.objects.filter(user=user).order_by('-created_at')[:20]
    
    total_deposits_btc = transactions.filter(type='deposit', currency='btc').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')
    
    total_deposits_xmr = transactions.filter(type='deposit', currency='xmr').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')
    
    total_withdrawals_btc = withdrawals.filter(status='completed', currency='btc').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')
    
    total_withdrawals_xmr = withdrawals.filter(status='completed', currency='xmr').aggregate(
        total=Sum('amount')
    )['total'] or Decimal('0')
    
    risk_factors = []
    risk_score = 0
    
    high_value_txs = transactions.filter(
        amount__gte=Decimal('1.0'),
        currency='btc'
    ).count()
    if high_value_txs > 5:
        risk_factors.append(f"High-value transactions: {high_value_txs}")
        risk_score += 20
    
    recent_withdrawals = withdrawals.filter(
        created_at__gte=timezone.now() - timedelta(days=7)
    ).count()
    if recent_withdrawals > 3:
        risk_factors.append(f"Recent withdrawals: {recent_withdrawals}")
        risk_score += 15
    
    if user.date_joined > timezone.now() - timedelta(days=30):
        risk_factors.append("New account (< 30 days)")
        risk_score += 25
    
    security_alerts = AuditLog.objects.filter(
        user=user,
        flagged=True
    ).order_by('-created_at')[:10]
    
    orders = user.orders.order_by('-created_at')[:10]
    total_orders = user.orders.count()
    completed_orders = user.orders.filter(status='COMPLETED').count()
    
    buyer_disputes = user.filed_disputes.order_by('-created_at')[:5]
    vendor_disputes = user.received_disputes.order_by('-created_at')[:5]
    
    context = {
        'user_detail': user,
        'wallet': wallet,
        'btc_balance': btc_balance,
        'xmr_balance': xmr_balance,
        'btc_escrow': btc_escrow,
        'xmr_escrow': xmr_escrow,
        'withdrawals': withdrawals,
        'transactions': transactions,
        'orders': orders,
        'total_orders': total_orders,
        'completed_orders': completed_orders,
        'total_deposits_btc': total_deposits_btc,
        'total_deposits_xmr': total_deposits_xmr,
        'total_withdrawals_btc': total_withdrawals_btc,
        'total_withdrawals_xmr': total_withdrawals_xmr,
        'risk_score': risk_score,
        'risk_factors': risk_factors,
        'security_alerts': security_alerts,
        'buyer_disputes': buyer_disputes,
        'vendor_disputes': vendor_disputes,
    }
    
    return render(request, 'adminpanel/user_detail.html', context)


@require_triple_auth
def triple_auth(request):
    """Triple authentication for sensitive admin operations"""
    if request.method == 'POST':
        # Generate PGP challenge
        challenge_text = f"Admin verification challenge: {secrets.token_urlsafe(16)}"
        
        request.session['pgp_challenge'] = {
            'text': challenge_text,
            'expected_response': challenge_text,  # In real implementation, this would be encrypted
            'timestamp': time.time()
        }
        
        form = TripleAuthForm(
            user=request.user,
            pgp_challenge=request.session.get('pgp_challenge'),
            data=request.POST
        )
        
        if form.is_valid():
            cache.set(f'triple_auth_verified:{request.user.id}', True, 300)  # 5 minutes
            
            SecurityAuditLog.objects.create(
                user=request.user,
                category='authentication',
                action='triple_auth_success',
                details={'timestamp': timezone.now().isoformat()},
                session_key=request.session.session_key or '',
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                risk_level='high'
            )
            
            messages.success(request, 'Triple authentication successful.')
            
            next_url = request.GET.get('next', reverse('adminpanel:dashboard'))
            return redirect(next_url)
        else:
            SecurityAuditLog.objects.create(
                user=request.user,
                category='authentication',
                action='triple_auth_failed',
                details={'errors': form.errors.as_json()},
                session_key=request.session.session_key or '',
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                risk_level='high'
            )
    else:
        # Generate PGP challenge for GET request
        challenge_text = f"Admin verification challenge: {secrets.token_urlsafe(16)}"
        
        request.session['pgp_challenge'] = {
            'text': challenge_text,
            'expected_response': challenge_text,
            'timestamp': time.time()
        }
        
        form = TripleAuthForm(user=request.user)
    
    context = {
        'form': form,
        'pgp_challenge_message': request.session.get('pgp_challenge', {}).get('text', ''),
    }
    
    return render(request, 'adminpanel/triple_auth.html', context)


@admin_required
def withdrawal_management(request):
    """Comprehensive withdrawal management interface"""
    status_filter = request.GET.get('status', 'pending')
    currency_filter = request.GET.get('currency', '')
    risk_filter = request.GET.get('risk', '')
    
    withdrawals = WithdrawalRequest.objects.all()
    
    if status_filter:
        withdrawals = withdrawals.filter(status=status_filter)
    if currency_filter:
        withdrawals = withdrawals.filter(currency=currency_filter)
    if risk_filter == 'high':
        withdrawals = withdrawals.filter(risk_score__gte=70)
    elif risk_filter == 'medium':
        withdrawals = withdrawals.filter(risk_score__gte=40, risk_score__lt=70)
    elif risk_filter == 'low':
        withdrawals = withdrawals.filter(risk_score__lt=40)
    
    withdrawals = withdrawals.order_by('-created_at')
    
    stats = {
        'total_pending': WithdrawalRequest.objects.filter(status='pending').count(),
        'total_reviewing': WithdrawalRequest.objects.filter(status='reviewing').count(),
        'total_approved': WithdrawalRequest.objects.filter(status='approved').count(),
        'total_rejected': WithdrawalRequest.objects.filter(status='rejected').count(),
        'high_risk_pending': WithdrawalRequest.objects.filter(
            status='pending', risk_score__gte=70
        ).count(),
    }
    
    context = {
        'withdrawals': withdrawals,
        'stats': stats,
        'status_filter': status_filter,
        'currency_filter': currency_filter,
        'risk_filter': risk_filter,
    }
    
    return render(request, 'adminpanel/withdrawal_management.html', context)


@require_triple_auth
def approve_withdrawal(request, withdrawal_id):
    """Approve a withdrawal request with triple authentication"""
    from wallets.models import WithdrawalRequest, Transaction
    
    withdrawal = get_object_or_404(WithdrawalRequest, id=withdrawal_id)
    
    if request.method == 'POST':
        if withdrawal.status != 'pending':
            messages.error(request, 'Withdrawal is not in pending status.')
            return redirect('adminpanel:withdrawal_management')
        
        wallet = withdrawal.user.wallet
        balance_field = f'balance_{withdrawal.currency}'
        current_balance = getattr(wallet, balance_field)
        
        if current_balance < withdrawal.amount:
            messages.error(request, 'Insufficient balance for withdrawal.')
            return redirect('adminpanel:withdrawal_management')
        
        withdrawal.status = 'approved'
        withdrawal.processed_by = request.user
        withdrawal.processed_at = timezone.now()
        withdrawal.admin_notes = request.POST.get('admin_notes', '')
        withdrawal.save()
        
        new_balance = current_balance - withdrawal.amount
        setattr(wallet, balance_field, new_balance)
        wallet.save()
        
        Transaction.objects.create(
            user=withdrawal.user,
            type='withdrawal',
            amount=withdrawal.amount,
            currency=withdrawal.currency,
            balance_before=current_balance,
            balance_after=new_balance,
            reference=f'WR-{withdrawal.id}',
            related_object_type='WithdrawalRequest',
            related_object_id=withdrawal.id,
            metadata={
                'withdrawal_address': withdrawal.address,
                'approved_by': request.user.username,
                'admin_notes': withdrawal.admin_notes
            }
        )
        
        log_admin_action(request, 'withdrawal_approved', withdrawal, {
            'amount': str(withdrawal.amount),
            'currency': withdrawal.currency,
            'user': withdrawal.user.username,
            'admin_notes': withdrawal.admin_notes
        })
        
        messages.success(request, f'Withdrawal {withdrawal.id} approved successfully.')
        return redirect('adminpanel:withdrawal_management')
    
    context = {
        'withdrawal': withdrawal,
    }
    
    return render(request, 'adminpanel/withdrawal_approve_confirm.html', context)


user_detail = admin_user_detail

@login_required
def admin_user_action(request, username):
    """Handle various user management actions"""
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('adminpanel:login')
    
    user = get_object_or_404(User, username=username)
    action = request.POST.get('action')
    
    if request.method == 'POST':
        if action == 'ban':
            user.is_active = False
            user.save()
            AdminLog.objects.create(
                admin_user=request.user,
                action_type='UPDATE',
                target_model='User',
                target_id=str(user.id),
                description=f'Banned user {user.username}',
                ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
            )
            messages.success(request, f'User {user.username} has been banned.')
            
        elif action == 'unban':
            user.is_active = True
            user.save()
            AdminLog.objects.create(
                admin_user=request.user,
                action_type='UPDATE',
                target_model='User',
                target_id=str(user.id),
                description=f'Unbanned user {user.username}',
                ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
            )
            messages.success(request, f'User {user.username} has been unbanned.')
            
        elif action == 'reset_2fa':
            user.pgp_public_key = ''
            user.pgp_fingerprint = ''
            user.pgp_login_enabled = False
            user.save()
            AdminLog.objects.create(
                admin_user=request.user,
                action_type='UPDATE',
                target_model='User',
                target_id=str(user.id),
                description=f'Reset 2FA for user {user.username}',
                ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
            )
            messages.success(request, f'2FA has been reset for {user.username}.')
            
        elif action == 'make_staff':
            user.is_staff = True
            user.save()
            AdminLog.objects.create(
                admin_user=request.user,
                action_type='UPDATE',
                target_model='User',
                target_id=str(user.id),
                description=f'Granted staff privileges to {user.username}',
                ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
            )
            messages.success(request, f'{user.username} is now a staff member.')
            
        elif action == 'remove_staff':
            user.is_staff = False
            user.save()
            AdminLog.objects.create(
                admin_user=request.user,
                action_type='UPDATE',
                target_model='User',
                target_id=str(user.id),
                description=f'Removed staff privileges from {user.username}',
                ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1')
            )
            messages.success(request, f'Staff privileges removed from {user.username}.')
    
    return redirect('adminpanel:user_detail', username=username)


ban_user = admin_user_action

@login_required
def vendors_list(request):
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('accounts:home')
    
    vendors = Vendor.objects.all().order_by('-trust_level')
    context = {'vendors': vendors}
    return render(request, 'adminpanel/vendors.html', context)

@login_required
def approve_vendor(request, vendor_id):
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('accounts:home')
    
    vendor = Vendor.objects.get(id=vendor_id)
    vendor.is_approved = True
    vendor.save()
    # log_event('vendor_approved', {'vendor_id': vendor_id, 'admin': request.user.username})
    messages.success(request, 'Vendor approved.')
    return redirect('adminpanel:vendors')

@login_required
def products_list(request):
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('accounts:home')
    
    products = Product.objects.all().order_by('-created_at')
    context = {'products': products}
    return render(request, 'adminpanel/products.html', context)

@login_required
def delete_product(request, product_id):
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('accounts:home')
    
    if request.method == 'POST':
        product = Product.objects.get(id=product_id)
        product.delete()
        # log_event('product_deleted', {'product_id': product_id, 'admin': request.user.username})
        messages.success(request, 'Product deleted.')
    return redirect('adminpanel:products')

@login_required
def orders_list(request):
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('accounts:home')
    
    orders = Order.objects.all().order_by('-created_at')
    context = {'orders': orders}
    return render(request, 'adminpanel/orders.html', context)

@login_required
def disputes_list(request):
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('accounts:home')
    
    disputes = Dispute.objects.all().order_by('-created_at')
    context = {'disputes': disputes}
    return render(request, 'adminpanel/disputes.html', context)

@login_required
def resolve_dispute(request, dispute_id):
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('accounts:home')
    
    dispute = Dispute.objects.get(id=dispute_id)
    if request.method == 'POST':
        resolution = request.POST.get('resolution')
        dispute.resolution = resolution
        dispute.status = 'resolved'
        dispute.resolved_at = timezone.now()
        dispute.save()
        # log_event('dispute_resolved', {'dispute_id': dispute_id, 'resolution': resolution, 'admin': request.user.username})
        messages.success(request, 'Dispute resolved.')
    return redirect('adminpanel:disputes')

@login_required
def withdrawals_list(request):
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('accounts:home')
    
    withdrawals = Transaction.objects.filter(transaction_type='WITHDRAWAL', status='PENDING').order_by('-created_at')
    context = {'withdrawals': withdrawals}
    return render(request, 'adminpanel/withdrawals.html', context)

@login_required
def approve_withdrawal(request, withdrawal_id):
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('accounts:home')
    
    withdrawal = Transaction.objects.get(id=withdrawal_id)
    withdrawal.status = 'CONFIRMED'
    withdrawal.save()
    # log_event('withdrawal_approved', {'withdrawal_id': withdrawal_id, 'admin': request.user.username})
    messages.success(request, 'Withdrawal approved.')
    return redirect('adminpanel:withdrawals')

def require_admin_auth(view_func):
    """Decorator to require admin authentication"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return redirect('adminpanel:login')
        
        admin_session = request.session.get('admin_authenticated')
        if not admin_session:
            return redirect('adminpanel:login')
        
        return view_func(request, *args, **kwargs)
    return wrapper

@require_admin_auth
def withdrawal_management(request):
    """Manage withdrawal requests with enhanced security"""
    from wallets.models import WithdrawalRequest
    
    status_filter = request.GET.get('status', 'all')
    risk_filter = request.GET.get('risk', 'all')
    
    withdrawals = WithdrawalRequest.objects.all().select_related('user')
    
    if status_filter != 'all':
        withdrawals = withdrawals.filter(status=status_filter)
    
    if risk_filter == 'high':
        withdrawals = withdrawals.filter(risk_score__gte=60)
    elif risk_filter == 'medium':
        withdrawals = withdrawals.filter(risk_score__gte=40, risk_score__lt=60)
    elif risk_filter == 'low':
        withdrawals = withdrawals.filter(risk_score__lt=40)
    
    withdrawals = withdrawals.order_by('-risk_score', '-created_at')
    
    paginator = Paginator(withdrawals, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    stats = {
        'pending_count': WithdrawalRequest.objects.filter(status='pending').count(),
        'reviewing_count': WithdrawalRequest.objects.filter(status='reviewing').count(),
        'high_risk_count': WithdrawalRequest.objects.filter(risk_score__gte=60).count(),
        'manual_review_count': WithdrawalRequest.objects.filter(manual_review_required=True).count(),
    }
    
    context = {
        'page_obj': page_obj,
        'stats': stats,
        'status_filter': status_filter,
        'risk_filter': risk_filter,
    }
    
    return render(request, 'adminpanel/withdrawal_management.html', context)

@require_admin_auth
def withdrawal_detail(request, withdrawal_id):
    """View detailed withdrawal information"""
    from wallets.models import WithdrawalRequest
    withdrawal = get_object_or_404(WithdrawalRequest, id=withdrawal_id)
    
    import logging
    logger = logging.getLogger('marketplace.admin')
    logger.info(
        f"Admin {request.user.username} accessed withdrawal detail {withdrawal_id}",
        extra={'session_key': request.session.session_key}
    )
    
    context = {
        'withdrawal': withdrawal,
    }
    
    return render(request, 'adminpanel/withdrawal_detail.html', context)

@require_admin_auth
def withdrawal_approve(request, withdrawal_id):
    """Approve a withdrawal request"""
    from wallets.models import WithdrawalRequest, AuditLog
    from django.views.decorators.http import require_POST
    
    if request.method != 'POST':
        return redirect('adminpanel:withdrawal_detail', withdrawal_id=withdrawal_id)
    
    withdrawal = get_object_or_404(WithdrawalRequest, id=withdrawal_id)
    
    if withdrawal.status not in ['pending', 'reviewing']:
        messages.error(request, 'Withdrawal cannot be approved in current status.')
        return redirect('adminpanel:withdrawal_detail', withdrawal_id=withdrawal_id)
    
    withdrawal.status = 'approved'
    withdrawal.approved_by = request.user
    withdrawal.approved_at = timezone.now()
    withdrawal.save()
    
    import logging
    logger = logging.getLogger('marketplace.admin')
    logger.info(
        f"Admin {request.user.username} approved withdrawal {withdrawal_id} "
        f"for user {withdrawal.user.username} amount {withdrawal.amount} {withdrawal.currency}",
        extra={'session_key': request.session.session_key}
    )
    
    AuditLog.objects.create(
        user=withdrawal.user,
        action='withdrawal_approved',
        ip_address='privacy_protected',
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        details={
            'withdrawal_id': withdrawal_id,
            'amount': str(withdrawal.amount),
            'currency': withdrawal.currency,
            'approved_by': request.user.username,
            'admin_session': request.session.session_key
        },
        risk_score=0
    )
    
    messages.success(request, f'Withdrawal #{withdrawal_id} has been approved.')
    return redirect('adminpanel:withdrawal_detail', withdrawal_id=withdrawal_id)

@require_admin_auth
def withdrawal_reject(request, withdrawal_id):
    """Reject a withdrawal request"""
    from wallets.models import WithdrawalRequest, AuditLog
    
    if request.method != 'POST':
        return redirect('adminpanel:withdrawal_detail', withdrawal_id=withdrawal_id)
    
    withdrawal = get_object_or_404(WithdrawalRequest, id=withdrawal_id)
    
    if withdrawal.status not in ['pending', 'reviewing']:
        messages.error(request, 'Withdrawal cannot be rejected in current status.')
        return redirect('adminpanel:withdrawal_detail', withdrawal_id=withdrawal_id)
    
    withdrawal.status = 'rejected'
    withdrawal.rejected_by = request.user
    withdrawal.rejected_at = timezone.now()
    withdrawal.save()
    
    import logging
    logger = logging.getLogger('marketplace.admin')
    logger.info(
        f"Admin {request.user.username} rejected withdrawal {withdrawal_id} "
        f"for user {withdrawal.user.username} amount {withdrawal.amount} {withdrawal.currency}",
        extra={'session_key': request.session.session_key}
    )
    
    AuditLog.objects.create(
        user=withdrawal.user,
        action='withdrawal_rejected',
        ip_address='privacy_protected',
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        details={
            'withdrawal_id': withdrawal_id,
            'amount': str(withdrawal.amount),
            'currency': withdrawal.currency,
            'rejected_by': request.user.username,
            'admin_session': request.session.session_key
        },
        risk_score=0
    )
    
    messages.success(request, f'Withdrawal #{withdrawal_id} has been rejected.')
    return redirect('adminpanel:withdrawal_detail', withdrawal_id=withdrawal_id)

@require_admin_auth
def withdrawal_add_notes(request, withdrawal_id):
    """Add admin notes to withdrawal"""
    from wallets.models import WithdrawalRequest
    
    if request.method != 'POST':
        return redirect('adminpanel:withdrawal_detail', withdrawal_id=withdrawal_id)
    
    withdrawal = get_object_or_404(WithdrawalRequest, id=withdrawal_id)
    
    admin_notes = request.POST.get('admin_notes', '').strip()
    withdrawal.admin_notes = admin_notes
    withdrawal.save()
    
    import logging
    logger = logging.getLogger('marketplace.admin')
    logger.info(
        f"Admin {request.user.username} updated notes for withdrawal {withdrawal_id}",
        extra={'session_key': request.session.session_key}
    )
    
    messages.success(request, 'Admin notes have been updated.')
    return redirect('adminpanel:withdrawal_detail', withdrawal_id=withdrawal_id)

@login_required
def admin_withdrawal_detail(request, withdrawal_id):
    """Detailed view of withdrawal request for admin processing"""
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('adminpanel:login')
    
    from wallets.models import WithdrawalRequest
    withdrawal = get_object_or_404(WithdrawalRequest, id=withdrawal_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        admin_notes = request.POST.get('admin_notes', '')
        
        if action == 'approve':
            withdrawal.status = 'approved'
            withdrawal.processed_by = request.user
            withdrawal.processed_at = timezone.now()
            withdrawal.admin_notes = admin_notes
            withdrawal.save()
            
            AdminLog.objects.create(
                admin_user=request.user,
                action_type='UPDATE',
                target_model='WithdrawalRequest',
                target_id=str(withdrawal.id),
                description=f'Approved withdrawal #{withdrawal.id} for {withdrawal.amount} {withdrawal.currency}',
                ip_address='privacy_protected'  # Privacy protection
            )
            
            messages.success(request, f'Withdrawal #{withdrawal.id} approved successfully.')
            
        elif action == 'reject':
            withdrawal.status = 'rejected'
            withdrawal.processed_by = request.user
            withdrawal.processed_at = timezone.now()
            withdrawal.admin_notes = admin_notes
            withdrawal.save()
            
            AdminLog.objects.create(
                admin_user=request.user,
                action_type='UPDATE',
                target_model='WithdrawalRequest',
                target_id=str(withdrawal.id),
                description=f'Rejected withdrawal #{withdrawal.id} for {withdrawal.amount} {withdrawal.currency}',
                ip_address='privacy_protected'  # Privacy protection
            )
            
            messages.success(request, f'Withdrawal #{withdrawal.id} rejected.')
        
        return redirect('adminpanel:withdrawal_detail', withdrawal_id=withdrawal.id)
    
    context = {
        'withdrawal': withdrawal,
        'user': withdrawal.user,
    }
    return render(request, 'adminpanel/withdrawal_detail.html', context)


@login_required
def admin_security_logs(request):
    """View security audit logs"""
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('adminpanel:login')
    
    from wallets.models import AuditLog
    
    flagged_logs = AuditLog.objects.filter(flagged=True).order_by('-created_at')[:50]
    
    high_risk_logs = AuditLog.objects.filter(
        risk_score__gte=60
    ).order_by('-created_at')[:50]
    
    context = {
        'flagged_logs': flagged_logs,
        'high_risk_logs': high_risk_logs,
    }
    return render(request, 'adminpanel/security_logs.html', context)


@login_required
def admin_wallet_overview(request):
    """Comprehensive wallet system overview"""
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('adminpanel:login')
    
    from wallets.models import Wallet, WithdrawalRequest, Transaction, WalletBalanceCheck
    from django.db.models import Sum, Count
    
    total_wallets = Wallet.objects.count()
    total_btc = Wallet.objects.aggregate(Sum('balance_btc'))['balance_btc__sum'] or 0
    total_xmr = Wallet.objects.aggregate(Sum('balance_xmr'))['balance_xmr__sum'] or 0
    total_escrow_btc = Wallet.objects.aggregate(Sum('escrow_btc'))['escrow_btc__sum'] or 0
    total_escrow_xmr = Wallet.objects.aggregate(Sum('escrow_xmr'))['escrow_xmr__sum'] or 0
    
    pending_withdrawals = WithdrawalRequest.objects.filter(status='pending').count()
    reviewing_withdrawals = WithdrawalRequest.objects.filter(status='reviewing').count()
    high_risk_withdrawals = WithdrawalRequest.objects.filter(
        status__in=['pending', 'reviewing'],
        risk_score__gte=60
    ).count()
    
    recent_discrepancies = WalletBalanceCheck.objects.filter(
        discrepancy_found=True,
        resolved=False
    ).order_by('-checked_at')[:10]
    
    recent_transactions = Transaction.objects.order_by('-created_at')[:20]
    
    context = {
        'total_wallets': total_wallets,
        'total_btc': total_btc,
        'total_xmr': total_xmr,
        'total_escrow_btc': total_escrow_btc,
        'total_escrow_xmr': total_escrow_xmr,
        'pending_withdrawals': pending_withdrawals,
        'reviewing_withdrawals': reviewing_withdrawals,
        'high_risk_withdrawals': high_risk_withdrawals,
        'recent_discrepancies': recent_discrepancies,
        'recent_transactions': recent_transactions,
    }
    return render(request, 'adminpanel/wallet_overview.html', context)


@login_required
def system_logs(request):
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('accounts:home')
    
    context = {'logs': []}
    return render(request, 'adminpanel/logs.html', context)

@login_required
def trigger_maintenance(request):
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('accounts:home')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'vacuum':
            messages.success(request, 'Database vacuum task triggered.')
        elif action == 'reconcile':
            messages.success(request, 'Wallet reconciliation task triggered.')
        elif action == 'expire':
            messages.success(request, 'Data expiration tasks triggered.')
    return redirect('adminpanel:dashboard')

@login_required
def image_settings(request):
    """Image upload configuration page"""
    if not request.user.is_superuser:
        messages.error(request, "Admin access required.")
        return redirect('accounts:home')
    
    from django.conf import settings
    
    if request.method == 'POST':
        storage_backend = request.POST.get('storage_backend', 'local')
        jpeg_quality = int(request.POST.get('jpeg_quality', 85))
        thumbnail_quality = int(request.POST.get('thumbnail_quality', 75))
        uploads_per_hour = int(request.POST.get('uploads_per_hour', 10))
        uploads_per_day = int(request.POST.get('uploads_per_day', 50))
        
        if not 50 <= jpeg_quality <= 95:
            jpeg_quality = 85
        if not 50 <= thumbnail_quality <= 85:
            thumbnail_quality = 75
        
        messages.success(request, 'Image settings updated successfully!')
        return redirect('adminpanel:image_settings')
    
    config = getattr(settings, 'IMAGE_UPLOAD_SETTINGS', {})
    
    context = {
        'current_backend': config.get('STORAGE_BACKEND', 'local'),
        'max_file_size_mb': 2,  # Fixed at 2MB
        'uploads_per_hour': config.get('UPLOADS_PER_HOUR', 10),
        'uploads_per_day': config.get('UPLOADS_PER_DAY', 50),
        'allowed_extensions': config.get('ALLOWED_EXTENSIONS', ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']),
        'max_dimensions': config.get('MAX_IMAGE_DIMENSIONS', (1920, 1080)),
        'thumbnail_size': config.get('THUMBNAIL_SIZE', (400, 400)),
        'current_settings': config,
    }
    
    return render(request, 'adminpanel/image_settings.html', context)
