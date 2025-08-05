from django.contrib import admin

from .models import (
    BroadcastMessage,
    VendorStats,
    Wallet,
    WalletAuditLog,
    WithdrawalRequest,
)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "btc_balance", "xmr_balance", "escrow_balance")


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "amount", "currency", "status", "created_at")
    actions = ["approve_withdrawals"]

    def approve_withdrawals(self, request, queryset):
        for withdrawal in queryset.filter(status="pending"):
            withdrawal.status = "approved"
            withdrawal.save()

    approve_withdrawals.short_description = "Approve selected withdrawals"


@admin.register(VendorStats)
class VendorStatsAdmin(admin.ModelAdmin):
    list_display = ("vendor", "total_sales", "total_orders", "rating")


@admin.register(BroadcastMessage)
class BroadcastMessageAdmin(admin.ModelAdmin):
    list_display = ("title", "target_group", "created_at")


@admin.register(WalletAuditLog)
class WalletAuditLogAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "amount", "currency", "timestamp")
