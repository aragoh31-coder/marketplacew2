import random
import time

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit

from core.logging.audit_logger import audit_logger
from core.security.sanitization import UniversalSanitizer

from .totp_forms import (
    BackupCodesRegenerateForm,
    TOTPDisableForm,
    TOTPSetupForm,
    TOTPVerificationForm,
)


@login_required
@ratelimit(key="user", rate="5/m", block=True)
@csrf_exempt
def totp_setup(request):
    if request.user.totp_enabled:
        messages.info(request, "Two-factor authentication is already enabled.")
        return redirect("accounts:totp_settings")

    request.user.generate_totp_secret()

    if request.method == "POST":
        from core.security.captcha_cutcircle import (
            init_captcha_session,
            validate_captcha,
        )

        click_x = UniversalSanitizer.sanitize_text(request.POST.get("captcha_click.x", ""))
        click_y = UniversalSanitizer.sanitize_text(request.POST.get("captcha_click.y", ""))

        if (
            not click_x
            or not click_y
            or not validate_captcha(request, click_x, click_y)
        ):
            img_b64 = init_captcha_session(request)
            form = TOTPSetupForm(request.user, request.POST)
            return render(
                request,
                "accounts/totp_setup.html",
                {
                    "form": form,
                    "manual_entry_key": request.user.totp_secret,
                    "captcha_img": img_b64,
                    "error": "Captcha failed",
                },
            )

        form = TOTPSetupForm(request.user, request.POST)
        if form.is_valid():
            request.user.totp_enabled = True
            request.user.save(update_fields=["totp_enabled"])

            backup_codes = request.user.generate_backup_codes()

            audit_logger.log_user_action(
                user=request.user,
                action="totp_enabled",
                details={"method": "authenticator_app"},
                request=request,
                risk_level="medium",
            )

            request.session.flush()
            login(request, request.user)

            messages.success(request, "Two-factor authentication enabled successfully!")
            return render(
                request,
                "accounts/totp_backup_codes.html",
                {"backup_codes": backup_codes, "is_setup": True},
            )
    else:
        form = TOTPSetupForm(request.user)

    from core.security.captcha_cutcircle import init_captcha_session, validate_captcha

    img_b64 = init_captcha_session(request)
    return render(
        request,
        "accounts/totp_setup.html",
        {
            "form": form,
            "manual_entry_key": request.user.totp_secret,
            "captcha_img": img_b64,
        },
    )


@login_required
def totp_settings(request):
    """TOTP settings management"""
    if not request.user.totp_enabled:
        return redirect("accounts:totp_setup")

    backup_codes_count = len(request.user.totp_backup_codes)

    return render(
        request,
        "accounts/totp_settings.html",
        {"backup_codes_count": backup_codes_count},
    )


@login_required
def totp_disable(request):
    """Disable TOTP 2FA"""
    if not request.user.totp_enabled:
        messages.info(request, "Two-factor authentication is not enabled.")
        return redirect("accounts:profile")

    if request.method == "POST":
        form = TOTPDisableForm(request.user, request.POST)
        if form.is_valid():
            request.user.disable_totp()

            audit_logger.log_user_action(
                user=request.user,
                action="totp_disabled",
                details={"method": "user_request"},
                request=request,
                risk_level="high",
            )

            messages.success(request, "Two-factor authentication has been disabled.")
            return redirect("accounts:profile")
    else:
        form = TOTPDisableForm(request.user)

    return render(request, "accounts/totp_disable.html", {"form": form})


@login_required
def regenerate_backup_codes(request):
    """Regenerate backup codes"""
    if not request.user.totp_enabled:
        messages.error(request, "Two-factor authentication is not enabled.")
        return redirect("accounts:profile")

    if request.method == "POST":
        form = TOTPDisableForm(request.user, request.POST)
        if form.is_valid():
            backup_codes = request.user.generate_backup_codes()

            audit_logger.log_user_action(
                user=request.user,
                action="backup_codes_regenerated",
                details={"codes_count": len(backup_codes)},
                request=request,
                risk_level="medium",
            )

            messages.success(
                request,
                "New backup codes have been generated. Please save them securely.",
            )

            return render(
                request,
                "accounts/totp_backup_codes.html",
                {"backup_codes": backup_codes, "is_regeneration": True},
            )
    else:
        form = TOTPDisableForm(request.user)

    return render(request, "accounts/regenerate_backup_codes.html", {"form": form})


def totp_verify(request):
    """Verify TOTP during login process"""
    user_id = request.session.get("totp_user_id")
    if not user_id:
        messages.error(request, "Session expired. Please log in again.")
        return redirect("accounts:login")

    from django.contrib.auth import get_user_model

    User = get_user_model()

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "Invalid session. Please log in again.")
        return redirect("accounts:login")

    if request.method == "POST":
        form = TOTPVerificationForm(user, request.POST)
        if form.is_valid():
            from django.contrib.auth import login

            login(request, user)

            request.session.pop("totp_user_id", None)
            request.session.pop("totp_required", None)

            audit_logger.log_user_action(
                user=user,
                action="totp_login_success",
                details={"method": "totp_verification"},
                request=request,
                risk_level="low",
            )

            messages.success(request, f"Welcome back, {user.username}!")

            next_url = request.session.pop("login_redirect_url", "/")
            return redirect(next_url)
        else:
            audit_logger.log_security_event(
                event_type="totp_verification_failed",
                risk_level="medium",
                details={"username": user.username},
                user=user,
                request=request,
            )
    else:
        form = TOTPVerificationForm(user)

    return render(request, "accounts/verify_totp.html", {"form": form, "user": user})


@require_http_methods(["POST"])
@login_required
def test_totp(request):
    """Test TOTP token (non-AJAX endpoint for Tor compatibility)"""
    if not request.user.totp_secret:
        messages.error(request, "TOTP not configured")
        return redirect("accounts:totp_setup")

    token = UniversalSanitizer.sanitize_text(request.POST.get("token", "").strip())

    if len(token) != 6 or not token.isdigit():
        messages.error(request, "Invalid token format")
        return redirect("accounts:totp_setup")

    is_valid = request.user.verify_totp(token)

    if is_valid:
        messages.success(request, "Token is valid!")
    else:
        messages.error(request, "Invalid token")
    
    return redirect("accounts:totp_setup")
