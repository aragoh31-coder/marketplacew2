from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from decimal import Decimal
from .models import Wallet, WithdrawalRequest


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'balance']
    search_fields = ['user__username']


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = ['user', 'amount', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'address']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
