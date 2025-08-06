import base64
import hashlib
import io
import json
import logging
import random
import secrets
import time
from datetime import datetime, timedelta

import pyotp
import qrcode
from dateutil import parser
from django import forms
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit
from PIL import Image, ImageDraw

from core.logging.audit_logger import audit_logger
from core.security.pow import validate_pow
from core.security.sanitization import UniversalSanitizer
from core.utils.cache import log_event
from products.models import Product

from .forms import DeleteAccountForm, LoginForm, PGPKeyForm, RegistrationForm
from .models import LoginHistory, User
from .pgp_service import PGPService
from .totp_utils import TOTPManager


class CaptchaSessionManager:
    """Manages CAPTCHA data in session with consistent JSON encoding to prevent type conversion issues"""

    @staticmethod
    def set_captcha(request, answer, question, image_data, expires):
        """Store CAPTCHA data in session with JSON encoding to force string storage"""
        captcha_data = {
            "answer": str(answer),
            "question": question,
            "image_data": image_data,
            "expires": (
                expires.isoformat() if hasattr(expires, "isoformat") else str(expires)
            ),
            "timestamp": time.time(),
        }
        request.session["captcha_data"] = json.dumps(captcha_data)
        request.session.save()
        print(f"DEBUG SET_CAPTCHA: Stored answer='{answer}', question='{question}'")

    @staticmethod
    def get_captcha(request):
        """Retrieve CAPTCHA data from session with JSON decoding"""
        data = request.session.get("captcha_data")
        if data:
            try:
                return json.loads(data)
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    @staticmethod
    def validate_captcha(request, user_answer):
        """Validate CAPTCHA answer with consistent string comparison"""
        captcha_data = CaptchaSessionManager.get_captcha(request)
        if not captcha_data:
            print("DEBUG VALIDATE_CAPTCHA: No captcha data found")
            return False

        try:
            expires_str = captcha_data.get("expires")
            if expires_str:
                if isinstance(expires_str, str):
                    expires = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                else:
                    expires = expires_str
                    if expires.tzinfo is None:
                        expires = timezone.make_aware(expires)

                current_time = timezone.now()
                print(
                    f"DEBUG VALIDATE_CAPTCHA: Current time: {current_time}, Expires: {expires}"
                )
                if current_time > expires:
                    print("DEBUG VALIDATE_CAPTCHA: CAPTCHA expired")
                    return False
                else:
                    print(
                        f"DEBUG VALIDATE_CAPTCHA: CAPTCHA still valid, {(expires - current_time).total_seconds()} seconds remaining"
                    )
        except (ValueError, TypeError) as e:
            print(f"DEBUG VALIDATE_CAPTCHA: Error parsing expiration: {e}")
            print(
                "DEBUG VALIDATE_CAPTCHA: Continuing validation despite expiration parsing error"
            )

        stored_answer = str(captcha_data.get("answer", ""))
        user_answer_str = str(user_answer).strip()

        print(
            f"DEBUG VALIDATE_CAPTCHA: Comparing '{user_answer_str}' == '{stored_answer}'"
        )
        print(
            f"DEBUG VALIDATE_CAPTCHA: user_answer_str type: {type(user_answer_str)}, len: {len(user_answer_str)}"
        )
        print(
            f"DEBUG VALIDATE_CAPTCHA: stored_answer type: {type(stored_answer)}, len: {len(stored_answer)}"
        )
        print(f"DEBUG VALIDATE_CAPTCHA: user_answer_str repr: {repr(user_answer_str)}")
        print(f"DEBUG VALIDATE_CAPTCHA: stored_answer repr: {repr(stored_answer)}")

        result = user_answer_str == stored_answer
        print(f"DEBUG VALIDATE_CAPTCHA: Comparison result: {result}")
        return result

    @staticmethod
    def clear_captcha(request):
        """Clear CAPTCHA data from session"""
        if "captcha_data" in request.session:
            del request.session["captcha_data"]

        old_keys = [
            "math_answer",
            "captcha_question",
            "captcha_generated",
            "form_hash",
            "captcha_hash",
            "captcha_timestamp",
            "captcha_answer",
            "captcha_expires",
        ]
        for key in old_keys:
            request.session.pop(key, None)

        request.session.save()


User = get_user_model()


class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)


class RegisterForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")


def generate_captcha():
    """Generate a simple math CAPTCHA question and answer"""
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    return f"{a} + {b}", str(a + b)


def generate_shape_captcha(width=200, height=80, ttl_minutes=30):
    """
    Draws N random shapes and returns:
      - question: str e.g. "How many triangles are in this image?"
      - answer: str (the integer count)
      - image_data: base64‐data URI to embed in an <img>
      - expires: datetime when this challenge should expire
    """
    shape = random.choice(["circle", "square", "triangle"])
    count = random.randint(3, 7)

    print(f"DEBUG GENERATE_CAPTCHA: Creating {count} {shape}s")

    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)

    def draw_one(x, y, s):
        if shape == "circle":
            draw.ellipse((x, y, x + s, y + s), outline="black", width=2)
        elif shape == "square":
            draw.rectangle((x, y, x + s, y + s), outline="black", width=2)
        else:  # triangle
            draw.polygon(
                [(x + s / 2, y), (x, y + s), (x + s, y + s)], outline="black", width=2
            )

    margin = 10
    max_s = min(width, height) // 4
    for _ in range(count):
        s = random.randint(20, max_s)
        x = random.randint(margin, width - margin - s)
        y = random.randint(margin, height - margin - s)
        draw_one(x, y, s)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    data_uri = f"data:image/png;base64,{b64}"

    question = f"How many {shape}s do you see?"
    answer = str(count)
    expires = timezone.now() + timedelta(minutes=ttl_minutes)

    print(f"DEBUG GENERATE_CAPTCHA: Generated question='{question}', answer='{answer}'")
    return question, answer, data_uri, expires


class CustomUserCreationForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(
        label="Password confirmation", widget=forms.PasswordInput
    )
    honeypot_field = forms.CharField(
        required=False, widget=forms.HiddenInput(), label=""
    )

    class Meta:
        model = User
        fields = ("username", "email")

    def clean_honeypot_field(self):
        honeypot = self.cleaned_data.get("honeypot_field")
        if honeypot:
            raise forms.ValidationError("Bot detected")
        return honeypot

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


def home(request):
    featured_products = Product.objects.filter(is_available=True)[:6]
    return render(request, "home.html", {"featured_products": featured_products})


@csrf_exempt
def register_view(request):
    print(f"DEBUG: register_view START with method: {request.method}", flush=True)

    from core.security.captcha_cutcircle import (
        init_captcha_session,
        validate_captcha,
        validate_captcha_with_transform,
    )

    print("DEBUG: CAPTCHA imports completed", flush=True)

    from django.shortcuts import redirect, render

    print("DEBUG: Django shortcuts imported", flush=True)

    from django.contrib import messages

    print("DEBUG: Django messages imported", flush=True)

    print(f"DEBUG: All imports done, method check: {request.method}", flush=True)
    print(f"DEBUG: About to check method conditions", flush=True)
    print(f"DEBUG: request.method == 'GET': {request.method == 'GET'}", flush=True)
    print(f"DEBUG: request.method == 'POST': {request.method == 'POST'}", flush=True)

    if request.method == "GET":
        print("DEBUG: Processing GET request", flush=True)
        img_b64 = init_captcha_session(request)
        print(f"DEBUG: Generated captcha image, length: {len(img_b64)}", flush=True)
        form = RegistrationForm()
        context = {"form": form, "captcha_img": img_b64}
        print(f"DEBUG: Template context keys: {list(context.keys())}", flush=True)
        print(f"DEBUG: About to render template: accounts/register.html", flush=True)
        return render(request, "accounts/register.html", context)

    elif request.method == "POST":
        print("DEBUG: Processing POST request", flush=True)
        print(f"DEBUG: POST data keys: {list(request.POST.keys())}", flush=True)
        print(f"DEBUG: POST data: {dict(request.POST)}", flush=True)
        print(f"DEBUG: POST data keys: {list(request.POST.keys())}", flush=True)
        print(f"DEBUG: POST data: {dict(request.POST)}", flush=True)

        click_x = UniversalSanitizer.sanitize_text(request.POST.get("captcha_click.x", ""))
        click_y = UniversalSanitizer.sanitize_text(request.POST.get("captcha_click.y", ""))

        print(f"DEBUG: Extracted coordinates - X: {click_x}, Y: {click_y}", flush=True)

        if not click_x or not click_y:
            img_b64 = init_captcha_session(request)
            form = RegistrationForm(request.POST)
            return render(
                request,
                "accounts/register.html",
                {
                    "form": form,
                    "error": "Please click on the cut circle to verify",
                    "captcha_img": img_b64,
                },
            )

        print(
            f"DEBUG: About to validate captcha with coordinates ({click_x}, {click_y})",
            flush=True,
        )
        captcha_result = validate_captcha(request, click_x, click_y)
        print(f"DEBUG: Captcha validation result: {captcha_result}", flush=True)

        if not captcha_result:
            print(f"DEBUG: CAPTCHA validation failed, regenerating", flush=True)
            img_b64 = init_captcha_session(request)
            form = RegistrationForm(request.POST)
            return render(
                request,
                "accounts/register.html",
                {
                    "form": form,
                    "error": "Please click on the circle with the cut/notch to verify you are human.",
                    "captcha_img": img_b64,
                },
            )

        form = RegistrationForm(request.POST)
        if form.is_valid():
            username = UniversalSanitizer.sanitize_text(form.cleaned_data["username"])
            password = UniversalSanitizer.sanitize_text(form.cleaned_data["password"])
            user = User.objects.create_user(username=username, password=password)
            messages.success(
                request, "Account created successfully! You can now log in."
            )
            return redirect("accounts:login")

        img_b64 = init_captcha_session(request)
        return render(
            request, "accounts/register.html", {"form": form, "captcha_img": img_b64}
        )

    print(f"DEBUG: Reached end of function with method: {request.method}", flush=True)
    print("DEBUG: No method condition matched - this should not happen", flush=True)


import random
import time

from django.http import HttpResponseForbidden
from django_ratelimit.decorators import ratelimit


@ratelimit(key="ip", rate="5/m", block=True)
@csrf_exempt
def login_view(request):
    from django.contrib.auth import authenticate, login
    from django.shortcuts import redirect, render

    from core.security.captcha_cutcircle import (
        init_captcha_session,
        validate_captcha,
        validate_captcha_with_transform,
    )

    from .forms import LoginForm

    print(f"DEBUG LOGIN VIEW: Method={request.method}, Path={request.path}")

    if request.method == "GET":
        img_b64 = init_captcha_session(request)
        form = LoginForm()
        return render(
            request, "accounts/login.html", {"form": form, "captcha_img": img_b64}
        )

    if request.method == "POST":
        print(f"DEBUG: POST data keys: {list(request.POST.keys())}", flush=True)
        print(f"DEBUG: POST data: {dict(request.POST)}", flush=True)

        click_x = UniversalSanitizer.sanitize_text(request.POST.get("captcha_click.x", ""))
        click_y = UniversalSanitizer.sanitize_text(request.POST.get("captcha_click.y", ""))

        print(f"DEBUG: Extracted coordinates - X: {click_x}, Y: {click_y}", flush=True)

        print(f"DEBUG LOGIN: Received POST data: {dict(request.POST)}")
        print(f"DEBUG LOGIN: Click coordinates: x={click_x}, y={click_y}")

        if not click_x or not click_y:
            print(f"DEBUG LOGIN: Missing coordinates, regenerating captcha")
            img_b64 = init_captcha_session(request)
            form = LoginForm(request.POST)
            return render(
                request,
                "accounts/login.html",
                {
                    "form": form,
                    "error": "Please click on the cut circle to verify",
                    "captcha_img": img_b64,
                },
            )

        print(
            f"DEBUG: About to validate captcha with coordinates ({click_x}, {click_y})",
            flush=True,
        )
        captcha_result = validate_captcha(request, click_x, click_y)
        print(f"DEBUG: Captcha validation result: {captcha_result}", flush=True)

        if not captcha_result:
            print(f"DEBUG: Login CAPTCHA validation failed, regenerating", flush=True)
            img_b64 = init_captcha_session(request)
            form = LoginForm(request.POST)
            return render(
                request,
                "accounts/login.html",
                {
                    "form": form,
                    "error": "Please click on the circle with the cut/notch to verify you are human.",
                    "captcha_img": img_b64,
                },
            )

        print(f"DEBUG LOGIN: Captcha passed, proceeding to form validation")

        form = LoginForm(request.POST)
        if form.is_valid():
            username = UniversalSanitizer.sanitize_text(form.cleaned_data["username"])
            password = UniversalSanitizer.sanitize_text(form.cleaned_data["password"])
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                return redirect("/")

        img_b64 = init_captcha_session(request)
        return render(
            request, "accounts/login.html", {"form": form, "captcha_img": img_b64}
        )


def old_login_view(request):
    if request.method in ["GET", "HEAD"]:
        form = LoginForm()

        CaptchaSessionManager.clear_captcha(request)

        q, a, img, exp = generate_shape_captcha()
        CaptchaSessionManager.set_captcha(request, a, q, img, exp)

        return render(
            request,
            "accounts/login.html",
            {
                "form": form,
                "captcha_question": q,
                "captcha_image": img,
            },
        )

    if request.method == "POST":
        form = LoginForm(request.POST)

        user_answer = UniversalSanitizer.sanitize_text(request.POST.get("captcha", "").strip())

        captcha_data = CaptchaSessionManager.get_captcha(request)
        print(
            f"DEBUG LOGIN CAPTCHA: User answered '{user_answer}' (type: {type(user_answer)})"
        )
        print(f"DEBUG LOGIN CAPTCHA: CAPTCHA data: {captcha_data}")

        captcha_valid = CaptchaSessionManager.validate_captcha(request, user_answer)
        print(f"DEBUG LOGIN CAPTCHA: Validation result: {captcha_valid}")

        if not captcha_valid:
            messages.error(request, "Incorrect CAPTCHA. Please try again.")

            CaptchaSessionManager.clear_captcha(request)
            q, a, img, exp = generate_shape_captcha()
            CaptchaSessionManager.set_captcha(request, a, q, img, exp)

            return render(
                request,
                "accounts/login.html",
                {
                    "form": form,
                    "captcha_question": q,
                    "captcha_image": img,
                },
            )

        CaptchaSessionManager.clear_captcha(request)

        if form.is_valid():
            username = UniversalSanitizer.sanitize_text(form.cleaned_data["username"])
            password = UniversalSanitizer.sanitize_text(form.cleaned_data["password"])

            user = authenticate(request, username=username, password=password)
            if user is not None:
                if user.requires_2fa():
                    request.session["pre_auth_user"] = user.id

                    if getattr(user, "totp_enabled", False):
                        return redirect("accounts:verify_totp")
                    elif getattr(user, "pgp_2fa_enabled", False) or (
                        user.pgp_login_enabled and user.pgp_public_key
                    ):
                        return redirect("accounts:pgp_challenge")
                else:
                    from wallets.models import AuditLog

                    AuditLog.objects.create(
                        user=user,
                        action="login",
                        details={
                            "login_method": "standard",
                            "username": username,
                            "2fa_enabled": user.requires_2fa(),
                            "ip_address": "privacy_protected",
                            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
                        },
                        risk_score=0,
                    )

                    login(request, user)
                    messages.success(request, f"Welcome back, {user.username}!")
                    return redirect("/")

                if user.pgp_login_enabled and user.pgp_public_key:
                    messages.info(
                        request,
                        "PGP functionality is currently disabled for security hardening.",
                    )
                    return redirect("accounts:login")

                    pgp_service = PGPService()
                    import_result = pgp_service.import_public_key(user.pgp_public_key)

                    if not import_result["success"]:
                        messages.error(
                            request,
                            "PGP key error. Please update your PGP key in settings.",
                        )
                        q, a, img, exp = generate_shape_captcha()
                        CaptchaSessionManager.set_captcha(request, a, q, img, exp)
                        return render(
                            request,
                            "accounts/login.html",
                            {
                                "form": form,
                                "captcha_question": q,
                                "captcha_image": img,
                            },
                        )

                    challenge = user.generate_pgp_challenge()
                    challenge_message = f"MARKETPLACE-2FA:{challenge}"

                    pgp_service = PGPService()
                    encrypt_result = pgp_service.encrypt_message(
                        challenge_message, user.pgp_fingerprint
                    )

                    if not encrypt_result["success"]:
                        messages.error(
                            request,
                            "Failed to generate PGP challenge. Please try again.",
                        )

                        q, a, img, exp = generate_shape_captcha()
                        CaptchaSessionManager.set_captcha(request, a, q, img, exp)

                        return render(
                            request,
                            "accounts/login.html",
                            {
                                "form": form,
                                "captcha_question": q,
                                "captcha_image": img,
                            },
                        )

                    request.session["pgp_2fa_user_id"] = str(user.id)
                    request.session["pgp_2fa_timestamp"] = timezone.now().isoformat()
                    request.session["pgp_2fa_encrypted_challenge"] = encrypt_result[
                        "encrypted_message"
                    ]

                    request.session.save()

                    return redirect("accounts:pgp_challenge")
                else:
                    login(request, user)

                    from wallets.models import Wallet

                    Wallet.objects.get_or_create(user=user)

                    LoginHistory.objects.create(
                        user=user,
                        ip_hash=hashlib.sha256(
                            "privacy_protected".encode()
                        ).hexdigest(),
                        user_agent=request.META.get("HTTP_USER_AGENT", "")[:200],
                        success=True,
                    )

                    messages.success(request, f"Welcome back, {username}!")
                    return redirect("/")
            else:
                messages.error(request, "Invalid username or password.")

                from wallets.models import AuditLog

                try:
                    failed_user = User.objects.get(username=username)
                    AuditLog.objects.create(
                        user=failed_user,
                        action="login_failed",
                        details={
                            "reason": "invalid_credentials",
                            "username": username,
                            "ip_address": "privacy_protected",
                            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:200],
                        },
                        risk_score=20,
                        flagged=True,
                    )
                except User.DoesNotExist:
                    pass

        q, a, img, exp = generate_shape_captcha()
        CaptchaSessionManager.set_captcha(request, a, q, img, exp)

        return render(
            request,
            "accounts/login.html",
            {
                "form": form,
                "captcha_question": q,
                "captcha_image": img,
            },
        )


def logout_view(request):
    if request.user.is_authenticated:
        log_event(
            "user_logout",
            {"user_id": str(request.user.id), "username": request.user.username},
        )
    logout(request)
    return redirect("/")


@login_required
def profile_view(request):
    user = request.user

    try:
        from orders.models import Order

        current_orders = Order.objects.filter(
            buyer=user, status__in=["created", "paid", "shipped"]
        ).count()
        total_orders = Order.objects.filter(buyer=user).count()
    except:
        current_orders = 0
        total_orders = 0

    try:
        from disputes.models import Dispute

        active_disputes = Dispute.objects.filter(
            order__buyer=user, status="open"
        ).count()
    except:
        active_disputes = 0

    login_history = LoginHistory.objects.filter(user=user, success=True)[:5]

    try:
        wallet = user.wallet
        btc_balance = wallet.balance_btc
        xmr_balance = wallet.balance_xmr
    except:
        btc_balance = 0
        xmr_balance = 0

    feedback_percentage = 0
    if user.total_trades > 0:
        feedback_percentage = (user.positive_feedback_count / user.total_trades) * 100

    context = {
        "user": user,
        "trust_level": user.get_trust_level(),
        "current_orders": current_orders,
        "total_orders": total_orders,
        "active_disputes": active_disputes,
        "login_history": login_history,
        "btc_balance": btc_balance,
        "xmr_balance": xmr_balance,
        "feedback_percentage": feedback_percentage,
    }

    return render(request, "accounts/profile.html", context)


@login_required
def profile(request):
    return redirect("accounts:profile_view")


@login_required
def profile_settings(request):
    if request.method == "POST":
        messages.success(request, "Profile settings updated successfully!")
        return redirect("accounts:profile")

    return render(request, "accounts/profile_settings.html", {"user": request.user})


@login_required
def change_password(request):
    if request.method == "POST":
        from django.contrib.auth.forms import PasswordChangeForm

        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password changed successfully!")
            return redirect("accounts:profile")
    else:
        from django.contrib.auth.forms import PasswordChangeForm

        form = PasswordChangeForm(request.user)

    return render(request, "accounts/change_password.html", {"form": form})


@login_required
def pgp_settings(request):
    """Handle PGP key upload with verification"""
    if request.method == "POST":
        if "verify_code" in request.POST:
            return pgp_verify_key(request)

        form = PGPKeyForm(request.POST, instance=request.user)
        if form.is_valid():
            request.session["temp_pgp_key"] = UniversalSanitizer.sanitize_text(form.cleaned_data["pgp_public_key"])
            request.session["temp_pgp_fingerprint"] = getattr(form, "fingerprint", None)
            request.session["temp_pgp_login_enabled"] = form.cleaned_data[
                "enable_pgp_login"
            ]

            verification_code = secrets.token_urlsafe(16)
            request.session["pgp_verification_code"] = verification_code
            request.session["pgp_verification_expires"] = (
                timezone.now() + timedelta(minutes=10)
            ).isoformat()

            pgp_service = PGPService()

            import_result = pgp_service.import_public_key(
                UniversalSanitizer.sanitize_text(form.cleaned_data["pgp_public_key"])
            )
            if not import_result["success"]:
                messages.error(
                    request,
                    f'Failed to import key for verification: {import_result["error"]}',
                )
                form = PGPKeyForm(
                    initial={
                        "pgp_public_key": request.user.pgp_public_key,
                        "enable_pgp_login": request.user.pgp_login_enabled,
                    }
                )
                return render(
                    request,
                    "accounts/pgp_settings.html",
                    {
                        "form": form,
                        "has_pgp": bool(request.user.pgp_public_key),
                        "pgp_fingerprint": request.user.pgp_fingerprint,
                    },
                )

            verification_message = (
                f"PGP Key Verification\n\n"
                f"Please decrypt this message to verify your key.\n"
                f"Verification Code: {verification_code}\n\n"
                f"Enter only the verification code above."
            )

            fingerprint = getattr(form, "fingerprint", import_result.get("fingerprint"))
            if not fingerprint:
                messages.error(
                    request, "Failed to get key fingerprint for verification."
                )
                form = PGPKeyForm(
                    initial={
                        "pgp_public_key": request.user.pgp_public_key,
                        "enable_pgp_login": request.user.pgp_login_enabled,
                    }
                )
                return render(
                    request,
                    "accounts/pgp_settings.html",
                    {
                        "form": form,
                        "has_pgp": bool(request.user.pgp_public_key),
                        "pgp_fingerprint": request.user.pgp_fingerprint,
                    },
                )

            encrypt_result = pgp_service.encrypt_message(
                verification_message, fingerprint
            )

            if encrypt_result["success"]:
                return render(
                    request,
                    "accounts/pgp_verify.html",
                    {
                        "encrypted_message": encrypt_result["encrypted_message"],
                        "fingerprint": fingerprint[:8] + "..." + fingerprint[-8:],
                        "key_info": getattr(form, "key_info", {}),
                    },
                )
            else:
                messages.error(
                    request,
                    f'Failed to encrypt verification message: {encrypt_result["error"]}',
                )
                form = PGPKeyForm(
                    initial={
                        "pgp_public_key": request.user.pgp_public_key,
                        "enable_pgp_login": request.user.pgp_login_enabled,
                    }
                )
    else:
        form = PGPKeyForm(
            initial={
                "pgp_public_key": request.user.pgp_public_key,
                "enable_pgp_login": request.user.pgp_login_enabled,
            }
        )

    return render(
        request,
        "accounts/pgp_settings.html",
        {
            "form": form,
            "has_pgp": bool(request.user.pgp_public_key),
            "pgp_fingerprint": request.user.pgp_fingerprint,
        },
    )


@login_required
@ratelimit(key="ip", rate="5/m", block=True)
def pgp_verify_key(request):
    """Verify PGP key by checking decryption capability"""
    if request.method == "POST":
        submitted_code = UniversalSanitizer.sanitize_text(request.POST.get("verify_code", "").strip())

        stored_code = request.session.get("pgp_verification_code")
        expires = request.session.get("pgp_verification_expires")
        temp_key = request.session.get("temp_pgp_key")
        temp_fingerprint = request.session.get("temp_pgp_fingerprint")
        temp_login_enabled = request.session.get("temp_pgp_login_enabled", False)

        if not all([stored_code, expires, temp_key]):
            messages.error(request, "Verification session expired. Please try again.")
            return redirect("accounts:pgp_settings")

        if timezone.now() > parser.parse(expires):
            messages.error(request, "Verification code expired. Please try again.")
            for key in [
                "pgp_verification_code",
                "pgp_verification_expires",
                "temp_pgp_key",
                "temp_pgp_fingerprint",
                "temp_pgp_login_enabled",
            ]:
                request.session.pop(key, None)
            return redirect("accounts:pgp_settings")

        if submitted_code == stored_code:
            request.user.pgp_public_key = temp_key
            request.user.pgp_fingerprint = temp_fingerprint
            request.user.pgp_login_enabled = temp_login_enabled
            request.user.save()

            for key in [
                "pgp_verification_code",
                "pgp_verification_expires",
                "temp_pgp_key",
                "temp_pgp_fingerprint",
                "temp_pgp_login_enabled",
            ]:
                request.session.pop(key, None)

            messages.success(request, "PGP key verified and saved successfully!")

            if temp_login_enabled:
                messages.info(
                    request,
                    "PGP 2FA is now active. You will need to decrypt a challenge on your next login.",
                )

            return redirect("accounts:profile")
        else:
            messages.error(
                request, "Invalid verification code. Please check your decryption."
            )

            pgp_service = PGPService()

            import_result = pgp_service.import_public_key(temp_key)
            if not import_result["success"]:
                messages.error(
                    request,
                    "Failed to re-encrypt verification message. Please try again.",
                )
                return redirect("accounts:pgp_settings")

            verification_message = (
                f"PGP Key Verification\n\n"
                f"Please decrypt this message to verify your key.\n"
                f"Verification Code: {stored_code}\n\n"
                f"Enter only the verification code above."
            )

            encrypt_result = pgp_service.encrypt_message(
                verification_message, temp_fingerprint
            )

            return render(
                request,
                "accounts/pgp_verify.html",
                {
                    "encrypted_message": encrypt_result["encrypted_message"],
                    "fingerprint": temp_fingerprint[:8] + "..." + temp_fingerprint[-8:],
                    "error": True,
                },
            )

    return redirect("accounts:pgp_settings")


@login_required
def pgp_remove_key(request):
    """Remove PGP key from account"""
    if request.method == "POST":
        from django.contrib.auth import authenticate

        password = UniversalSanitizer.sanitize_text(request.POST.get("password", ""))

        if authenticate(username=request.user.username, password=password):
            request.user.pgp_public_key = ""
            request.user.pgp_fingerprint = ""
            request.user.pgp_login_enabled = False
            request.user.save()

            messages.success(request, "PGP key removed successfully.")
        else:
            messages.error(request, "Invalid password.")

    return redirect("accounts:pgp_settings")


@login_required
def delete_account(request):
    if request.method == "POST":
        form = DeleteAccountForm(request.POST)
        if form.is_valid():
            if not request.user.check_password(UniversalSanitizer.sanitize_text(form.cleaned_data["password"])):
                messages.error(request, "Incorrect password")
                return render(request, "accounts/delete_account.html", {"form": form})

            try:
                from orders.models import Order

                active_orders = Order.objects.filter(
                    buyer=request.user, status__in=["created", "paid", "shipped"]
                ).exists()

                if active_orders:
                    messages.error(request, "Cannot delete account with active orders")
                    return render(
                        request, "accounts/delete_account.html", {"form": form}
                    )
            except:
                pass

            with transaction.atomic():
                user = request.user

                log_event(
                    "account_deleted",
                    {"user_id": str(user.id), "username": user.username},
                )

                logout(request)

                user.delete()

                messages.success(request, "Account deleted successfully")
                return redirect("/")
    else:
        form = DeleteAccountForm()

    return render(request, "accounts/delete_account.html", {"form": form})


@login_required
def login_history_view(request):
    history = LoginHistory.objects.filter(user=request.user).order_by("-login_time")[:5]
    return render(request, "accounts/login_history.html", {"history": history})


@login_required
def test_pgp_encryption(request):
    """Test PGP encryption for debugging"""
    messages.info(
        request, "PGP functionality is currently disabled for security hardening."
    )
    return redirect("accounts:profile")

    pgp_service = PGPService()
    import_result = pgp_service.import_public_key(request.user.pgp_public_key)
    if not import_result["success"]:
        messages.error(request, f'Failed to import key: {import_result["error"]}')
        return redirect("accounts:pgp_settings")

    test_message = (
        "This is a test message from the marketplace.\nTimestamp: "
        + timezone.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    )
    pgp_service = PGPService()
    encrypt_result = pgp_service.encrypt_message(
        test_message, request.user.pgp_fingerprint
    )

    if encrypt_result["success"]:
        return render(
            request,
            "accounts/pgp_test.html",
            {
                "encrypted_message": encrypt_result["encrypted_message"],
                "original_message": test_message,
                "fingerprint": request.user.pgp_fingerprint,
            },
        )
    else:
        messages.error(request, f'Encryption failed: {encrypt_result["error"]}')
        return redirect("accounts:pgp_settings")


@ratelimit(key="ip", rate="5/m", block=True)
def pgp_challenge_view(request):
    """Handle PGP 2FA challenge verification with enhanced session persistence"""
    logger = logging.getLogger(__name__)

    logger.debug(f"DEBUG: pgp_challenge_view called with method: {request.method}")
    logger.debug(f"DEBUG: Session keys: {list(request.session.keys())}")

    user_id = request.session.get("pgp_2fa_user_id")
    timestamp = request.session.get("pgp_2fa_timestamp")
    encrypted_challenge = request.session.get("pgp_2fa_encrypted_challenge")

    logger.debug(f"DEBUG: user_id from session: {user_id}")
    logger.debug(f"DEBUG: timestamp from session: {timestamp}")
    logger.debug(f"DEBUG: encrypted_challenge present: {bool(encrypted_challenge)}")

    if not user_id or not timestamp or not encrypted_challenge:
        logger.debug("DEBUG: Missing session data, redirecting to login")
        messages.error(request, "No pending 2FA authentication")
        return redirect("accounts:login")

    from dateutil import parser

    session_time = parser.parse(timestamp)
    if timezone.now() - session_time > timedelta(minutes=15):
        messages.error(request, "2FA session expired. Please login again.")
        request.session.pop("pgp_2fa_user_id", None)
        request.session.pop("pgp_2fa_timestamp", None)
        request.session.pop("pgp_2fa_encrypted_challenge", None)
        return redirect("accounts:login")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "Invalid session")
        return redirect("accounts:login")

    time_remaining = 15 - int((timezone.now() - session_time).total_seconds() / 60)

    if request.method == "POST":
        decrypted_response = UniversalSanitizer.sanitize_text(request.POST.get("decrypted_response", "").strip())

        if not decrypted_response:
            messages.error(request, "Please provide the decrypted challenge")
            return render(
                request,
                "accounts/pgp_challenge.html",
                {
                    "username": user.username,
                    "encrypted_challenge": encrypted_challenge,
                    "challenge_format": "MARKETPLACE-2FA:XXXXXXXXXXXXX",
                    "time_remaining": time_remaining,
                },
            )

        challenge_code = None

        logger.debug(f"DEBUG: Received decrypted_response = {repr(decrypted_response)}")
        logger.debug(f"DEBUG: Current user.pgp_challenge = {repr(user.pgp_challenge)}")
        logger.debug(f"DEBUG: Challenge expires at = {user.pgp_challenge_expires}")

        if decrypted_response.startswith("MARKETPLACE-2FA:"):
            challenge_code = decrypted_response.replace("MARKETPLACE-2FA:", "").strip()
        elif len(decrypted_response) >= 32:  # Just the challenge code (allow longer)
            challenge_code = decrypted_response.strip()
        else:
            if "MARKETPLACE-2FA:" in decrypted_response:
                parts = decrypted_response.split("MARKETPLACE-2FA:")
                if len(parts) > 1:
                    challenge_code = parts[1].strip()

        logger.debug(f"DEBUG: Extracted challenge_code = {repr(challenge_code)}")

        if challenge_code and user.verify_pgp_challenge(challenge_code):
            login(request, user)

            request.session.pop("pgp_2fa_user_id", None)
            request.session.pop("pgp_2fa_timestamp", None)
            request.session.pop("pgp_2fa_encrypted_challenge", None)

            LoginHistory.objects.create(
                user=user,
                ip_hash=hashlib.sha256(
                    request.META.get("REMOTE_ADDR", "").encode()
                ).hexdigest(),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:200],
                success=True,
            )

            messages.success(request, "PGP authentication successful!")
            return redirect("/")
        else:
            messages.error(request, "Invalid challenge code. Please try again.")
            logger.warning(f"Invalid PGP challenge attempt for user {user.username}")

    return render(
        request,
        "accounts/pgp_challenge.html",
        {
            "username": user.username,
            "encrypted_challenge": encrypted_challenge,
            "challenge_format": "MARKETPLACE-2FA:XXXXXXXXXXXXX",
            "time_remaining": time_remaining,
        },
    )


@login_required
@never_cache
def totp_settings(request):
    """TOTP settings management"""
    user = request.user

    if request.method == "POST":
        action = UniversalSanitizer.sanitize_text(request.POST.get("action", ""))

        if action == "generate":
            if not getattr(user, "totp_enabled", False):
                user.totp_secret = TOTPManager.generate_secret()
                user.totp_backup_codes = TOTPManager.generate_backup_codes()
                user.save()
                messages.success(
                    request, "TOTP secret generated. Complete setup to enable."
                )
                return redirect("accounts:totp_setup")

        elif action == "disable":
            password = UniversalSanitizer.sanitize_text(request.POST.get("password", ""))
            if user.check_password(password):
                user.totp_enabled = False
                user.totp_secret = None
                user.totp_backup_codes = []
                user.totp_failure_count = 0
                user.last_totp_failure = None
                user.save()
                messages.success(request, "TOTP authentication disabled.")
            else:
                messages.error(request, "Incorrect password.")

    return render(
        request,
        "accounts/totp_settings.html",
        {
            "has_secret": bool(
                getattr(user, "totp_secret", None)
                and not getattr(user, "totp_enabled", False)
            )
        },
    )


@login_required
@never_cache
def totp_setup(request):
    """TOTP setup process"""
    user = request.user

    if not getattr(user, "totp_secret", None):
        return redirect("accounts:totp_settings")

    if getattr(user, "totp_enabled", False):
        messages.info(request, "TOTP is already enabled.")
        return redirect("accounts:totp_settings")

    if request.method == "POST":
        code = UniversalSanitizer.sanitize_text(request.POST.get("code", "").strip())

        if TOTPManager.verify_code(user.totp_secret, code):
            user.totp_enabled = True
            user.save()
            messages.success(request, "TOTP authentication enabled successfully!")
            return redirect("accounts:totp_backup_codes")
        else:
            messages.error(
                request, "Invalid code. Please check your authenticator app."
            )

    current_code = TOTPManager.get_current_code(user.totp_secret)

    return render(
        request,
        "accounts/totp_setup.html",
        {
            "secret": user.totp_secret,
            "current_code": current_code,
            "site_name": "DarkMarket",
        },
    )


@login_required
@never_cache
def totp_backup_codes(request):
    """Display backup codes (only shown once)"""
    user = request.user

    if not getattr(user, "totp_enabled", False) or not getattr(
        user, "totp_backup_codes", None
    ):
        return redirect("accounts:totp_settings")

    codes = user.totp_backup_codes.copy()

    if request.method == "POST":
        return redirect("accounts:profile_settings")

    return render(request, "accounts/totp_backup_codes.html", {"codes": codes})


@csrf_protect
@never_cache
def verify_totp(request):
    """TOTP verification during login"""
    user_id = request.session.get("pre_auth_user")
    if not user_id:
        return redirect("accounts:login")

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return redirect("accounts:login")

    allowed, lockout_until = TOTPManager.check_rate_limit(user)
    if not allowed:
        messages.error(
            request,
            f"Too many failed attempts. Try again after {lockout_until.strftime('%H:%M')}.",
        )
        return render(request, "accounts/verify_totp.html", {"locked": True})

    if request.method == "POST":
        code = UniversalSanitizer.sanitize_text(request.POST.get("code", "").strip())
        use_backup = UniversalSanitizer.sanitize_text(request.POST.get("use_backup", "")) == "1"

        verified = False

        if use_backup:
            backup_codes = getattr(user, "totp_backup_codes", [])
            if code in backup_codes:
                backup_codes.remove(code)
                user.totp_backup_codes = backup_codes
                user.save()
                verified = True
                messages.info(
                    request, f"Backup code used. {len(backup_codes)} codes remaining."
                )
        else:
            verified = TOTPManager.verify_code(getattr(user, "totp_secret", None), code)

        if verified:
            user.totp_failure_count = 0
            user.last_totp_failure = None
            user.save()

            login(request, user)
            request.session.pop("pre_auth_user", None)

            if getattr(user, "pgp_2fa_enabled", False):
                request.session["totp_verified"] = True
                return redirect("accounts:pgp_challenge")

            return redirect("/")
        else:
            with transaction.atomic():
                user.totp_failure_count = getattr(user, "totp_failure_count", 0) + 1
                user.last_totp_failure = timezone.now()
                user.save()

            messages.error(request, "Invalid code. Please try again.")

    return render(
        request,
        "accounts/verify_totp.html",
        {"attempts_remaining": 5 - getattr(user, "totp_failure_count", 0)},
    )
