from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.cache import cache
from django.urls import reverse
from django.http import HttpResponseRedirect
import logging

logger = logging.getLogger('marketplace.admin')


def require_2fa(view_func):
    """Decorator to require 2FA for sensitive operations"""
    @wraps(view_func)
    def wrapped_view(self, request, *args, **kwargs):
        if not hasattr(request.user, 'wallet') or not request.user.wallet.two_fa_enabled:
            messages.error(request, "2FA must be enabled for this action")
            return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/admin/'))
        
        cache_key = f'2fa_verified:{request.user.id}'
        if not cache.get(cache_key):
            messages.error(request, "Please verify 2FA before performing this action")
            return HttpResponseRedirect(reverse('adminpanel:verify_2fa') + f'?next={request.path}')
        
        return view_func(self, request, *args, **kwargs)
    
    return wrapped_view


def require_triple_auth(view_func):
    """Decorator requiring triple authentication for admin actions"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return redirect('adminpanel:login')
        
        cache_key = f'triple_auth_verified:{request.user.id}'
        if not cache.get(cache_key):
            messages.warning(request, 'Triple authentication required for this action.')
            return redirect('adminpanel:triple_auth')
        
        return view_func(request, *args, **kwargs)
    
    return wrapped_view


def log_admin_action(request, action, target_object=None, details=None):
    """Log admin actions for audit trail"""
    from .models import AdminLog
    
    try:
        AdminLog.objects.create(
            admin_user=request.user,
            action=action,
            target_model=target_object.__class__.__name__ if target_object else '',
            target_id=target_object.id if target_object and hasattr(target_object, 'id') else None,
            details=details or {},
            ip_address='privacy_protected',  # No IP logging for privacy
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:500]
        )
        logger.info(f"Admin action logged: {action} by {request.user.username}")
    except Exception as e:
        logger.error(f"Failed to log admin action: {e}")


def admin_required(view_func):
    """Decorator to ensure user is admin"""
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('adminpanel:login')
        
        if not request.user.is_superuser:
            messages.error(request, 'Admin access required.')
            return redirect('home')
        
        return view_func(request, *args, **kwargs)
    
    return wrapped_view
