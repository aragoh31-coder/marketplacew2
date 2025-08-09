import logging

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.generic import FormView

from core.utils.security import get_session_hash
from .forms import SecureLoginForm, SecureRegistrationForm
from .utils import detect_suspicious_patterns, log_security_event

logger = logging.getLogger("wallet.security")


@method_decorator([csrf_protect, never_cache], name="dispatch")
class SecureLoginView(FormView):
    """Enhanced login view with security features"""

    template_name = "accounts/login.html"
    form_class = SecureLoginForm
    success_url = reverse_lazy("core:home")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        username = form.cleaned_data.get("username")
        password = form.cleaned_data.get("password")

        user = authenticate(self.request, username=username, password=password)

        if user is not None:
            suspicious_score = detect_suspicious_patterns(
                user,
                "login",
                {
                    "session_hash": get_session_hash(self.request),
                    "user_agent": self.request.META.get("HTTP_USER_AGENT", ""),
                    "timestamp": timezone.now(),
                },
            )

            log_security_event(
                user,
                "login_attempt",
                {
                    "success": True,
                    "session_hash": get_session_hash(self.request),
                    "user_agent": self.request.META.get("HTTP_USER_AGENT", ""),
                    "suspicious_score": suspicious_score,
                },
                risk_score=suspicious_score,
            )

            self.request.session["login_session_hash"] = get_session_hash(self.request)
            self.request.session["login_time"] = timezone.now().timestamp()

            login(self.request, user)

            if suspicious_score > 50:
                messages.warning(
                    self.request,
                    "Unusual login detected. Additional security verification may be required.",
                )
                return redirect("security:security_verification")

            messages.success(self.request, f"Welcome back, {user.username}!")
            return super().form_valid(form)
        else:
            log_security_event(
                None,
                "failed_login",
                {
                    "username": username,
                    "session_hash": get_session_hash(self.request),
                    "user_agent": self.request.META.get("HTTP_USER_AGENT", ""),
                },
                risk_score=30,
            )

            messages.error(self.request, "Invalid username or password.")
            return self.form_invalid(form)



@method_decorator([csrf_protect, never_cache], name="dispatch")
class SecureRegistrationView(FormView):
    """Enhanced registration view with security features"""

    template_name = "accounts/register.html"
    form_class = SecureRegistrationForm
    success_url = reverse_lazy("accounts:login")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        user = form.save()

        log_security_event(
            user,
            "registration",
            {
                "session_hash": get_session_hash(self.request),
                "user_agent": self.request.META.get("HTTP_USER_AGENT", ""),
                "email": user.email,
            },
            risk_score=10,
        )

        from wallets.models import Wallet

        Wallet.objects.create(user=user)

        messages.success(
            self.request, "Registration successful! You can now log in to your account."
        )

        return super().form_valid(form)
