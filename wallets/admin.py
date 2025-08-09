from django.contrib import admin, messages
from django.db import transaction
from django.utils import timezone

from .models import Wallet, WalletAuditLog, WithdrawalRequest, VendorStats, BroadcastMessage


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "amount", "currency", "address", "status", "created_at", "processed_at")
    list_filter = ("status", "currency", "created_at")
    search_fields = ("user__username", "address")
    actions = ["approve_withdrawals", "deny_withdrawals"]

    @transaction.atomic
    def approve_withdrawals(self, request, queryset):
        approved = 0
        for wr in queryset.select_for_update():
            if wr.status != "pending":
                continue
            wallet = Wallet.objects.select_for_update().get(user=wr.user)
            if wallet.escrow_balance < wr.amount:
                messages.error(request, f"Insufficient escrow for request #{wr.id}")
                continue
            wallet.escrow_balance -= wr.amount
            wallet.save(update_fields=["escrow_balance"])
            wr.status = "approved"
            wr.processed_at = timezone.now()
            wr.save(update_fields=["status", "processed_at"])
            WalletAuditLog.objects.create(
                user=wr.user,
                action="withdrawal_approved",
                amount=wr.amount,
                currency=wr.currency,
                metadata={"request_id": wr.id, "by": request.user.username},
            )
            approved += 1
        self.message_user(request, f"Approved {approved} withdrawal(s).", level=messages.SUCCESS)

    approve_withdrawals.short_description = "Approve selected withdrawals"

    @transaction.atomic
    def deny_withdrawals(self, request, queryset):
        denied = 0
        for wr in queryset.select_for_update():
            if wr.status != "pending":
                continue
            wr.status = "denied"
            wr.processed_at = None
            wr.save(update_fields=["status", "processed_at"])
            WalletAuditLog.objects.create(
                user=wr.user,
                action="withdrawal_denied",
                amount=wr.amount,
                currency=wr.currency,
                metadata={"request_id": wr.id, "by": request.user.username},
            )
            denied += 1
        self.message_user(request, f"Denied {denied} withdrawal(s).", level=messages.WARNING)

    deny_withdrawals.short_description = "Deny selected withdrawals"
