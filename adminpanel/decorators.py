import logging
from functools import wraps

from django.contrib import messages
from django.core.cache import cache
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse

from core.security.sanitization import UniversalSanitizer

logger = logging.getLogger("marketplace.admin")


def require_2fa(view_func):
    """Decorator to require 2FA for sensitive operations"""

    @wraps(view_func)
    def wrapped_view(self, request, *args, **kwargs):
        if not request.user.totp_enabled:
            messages.error(request, "2FA must be enabled for this action")
            return HttpResponseRedirect(reverse("accounts:totp_setup"))

        cache_key = f"2fa_verified:{request.user.id}:{request.session.session_key}"
        if not cache.get(cache_key):
            totp_code = UniversalSanitizer.sanitize_text(request.POST.get("totp_code", "").strip())
            if not totp_code:
                messages.error(request, "Please verify 2FA before performing this action")
                return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/admin/"))
            
            if not request.user.verify_totp(totp_code):
                messages.error(request, "Invalid 2FA code")
                return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/admin/"))
            
            cache.set(cache_key, True, 300)

        return view_func(self, request, *args, **kwargs)

    return wrapped_view


def require_triple_auth(view_func):
    """Decorator requiring triple authentication for admin actions"""

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return redirect("adminpanel:login")

        cache_key = f"triple_auth_verified:{request.user.id}:{request.session.session_key}"
        if not cache.get(cache_key):
            from django.conf import settings
            admin_config = getattr(settings, 'ADMIN_SECURITY', {})
            
            if admin_config.get('REQUIRE_TRIPLE_AUTH', True):
                if request.method == 'POST':
                    password = UniversalSanitizer.sanitize_text(request.POST.get('admin_password', '').strip())
                    totp_code = UniversalSanitizer.sanitize_text(request.POST.get('totp_code', '').strip())
                    pgp_response = UniversalSanitizer.sanitize_text(request.POST.get('pgp_response', '').strip())
                    
                    if not password or not request.user.check_password(password):
                        messages.error(request, "Invalid admin password")
                        return redirect("adminpanel:triple_auth")
                    
                    if request.user.totp_enabled:
                        if not totp_code or not request.user.verify_totp(totp_code):
                            messages.error(request, "Invalid 2FA code")
                            return redirect("adminpanel:triple_auth")
                    
                    if request.user.pgp_public_key and admin_config.get('PGP_CHALLENGE_REQUIRED', True):
                        if not pgp_response or not request.user.verify_pgp_challenge(pgp_response):
                            messages.error(request, "Invalid PGP challenge response")
                            return redirect("adminpanel:triple_auth")
                    
                    cache.set(cache_key, True, admin_config.get('SESSION_TIMEOUT_MINUTES', 15) * 60)
                else:
                    messages.warning(request, "Triple authentication required for this action.")
                    return redirect("adminpanel:triple_auth")

        return view_func(request, *args, **kwargs)

    return wrapped_view


def log_admin_action(request, action, target_object=None, details=None):
    """Log admin actions for audit trail"""
    from .models import AdminLog

    try:
        AdminLog.objects.create(
            admin_user=request.user,
            action=action,
            target_model=target_object.__class__.__name__ if target_object else "",
            target_id=(
                target_object.id
                if target_object and hasattr(target_object, "id")
                else None
            ),
            details=details or {},
            ip_address="privacy_protected",  # No IP logging for privacy
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500],
        )
        logger.info(f"Admin action logged: {action} by {request.user.username}")
    except Exception as e:
        logger.error(f"Failed to log admin action: {e}")


def admin_required(view_func):
    """Decorator to ensure user is admin"""

    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("adminpanel:login")

        if not request.user.is_superuser:
            messages.error(request, "Admin access required.")
            return redirect("home")

        return view_func(request, *args, **kwargs)

    return wrapped_view
