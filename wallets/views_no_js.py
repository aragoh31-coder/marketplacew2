from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from core.security.sanitization import UniversalSanitizer
from .models import BroadcastMessage, Wallet, WalletAuditLog, WithdrawalRequest


@login_required
def dashboard(request):
    wallet, created = Wallet.objects.get_or_create(user=request.user)
    withdrawals = WithdrawalRequest.objects.filter(user=request.user).order_by(
        "-created_at"
    )[:10]
    return render(
        request,
        "wallets/dashboard_no_js.html",
        {"wallet": wallet, "withdrawals": withdrawals},
    )


@login_required
@transaction.atomic
def request_withdrawal(request):
    if request.method == "POST":
        amount = Decimal(UniversalSanitizer.sanitize_text(request.POST.get("amount", "0")))
        currency = UniversalSanitizer.sanitize_text(request.POST.get("currency", ""))
        address = UniversalSanitizer.sanitize_text(request.POST.get("address", ""))
        wallet, created = Wallet.objects.get_or_create(user=request.user)
        if getattr(wallet, f"{currency}_balance") < amount:
            messages.error(request, "Insufficient balance")
            return redirect("wallets:dashboard")
        setattr(
            wallet,
            f"{currency}_balance",
            getattr(wallet, f"{currency}_balance") - amount,
        )
        wallet.save()
        WithdrawalRequest.objects.create(
            user=request.user, amount=amount, currency=currency, address=address
        )
        WalletAuditLog.create_log(request.user, amount, currency, "withdrawal")
        messages.success(request, "Withdrawal request submitted.")
    return redirect("wallets:dashboard")


@login_required
def broadcast_messages(request):
    messages_list = BroadcastMessage.objects.all().order_by("-created_at")[:10]
    return render(request, "wallets/broadcast_list.html", {"messages": messages_list})
