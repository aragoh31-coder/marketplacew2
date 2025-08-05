from functools import wraps

import pyotp
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect


def require_vendor(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not hasattr(request.user, "vendor"):
            return HttpResponseForbidden("Vendor access required")
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def require_signed_url(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def require_2fa(view_func):
    """Decorator to require 2FA verification for admin actions"""

    @wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        if hasattr(request.user, "wallet") and request.user.wallet.two_fa_enabled:
            two_fa_code = request.POST.get("two_fa_code")
            if not two_fa_code:
                messages.error(request, "2FA code required for this action")
                return redirect(request.META.get("HTTP_REFERER", "/admin/"))

            totp = pyotp.TOTP(request.user.wallet.two_fa_secret)
            if not totp.verify(two_fa_code):
                messages.error(request, "Invalid 2FA code")
                return redirect(request.META.get("HTTP_REFERER", "/admin/"))

        return view_func(self, request, *args, **kwargs)

    return wrapper
