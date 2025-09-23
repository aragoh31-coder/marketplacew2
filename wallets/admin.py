from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db import transaction
from django.contrib import messages
from .models import (
    Wallet, WithdrawalRequest, Transaction, 
    ConversionRate, AuditLog, WalletBalanceCheck
)


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'balance_btc_display', 'balance_xmr_display',
        'escrow_btc_display', 'escrow_xmr_display', 'last_activity'
    ]
    list_filter = ['two_fa_enabled', 'created_at', 'last_activity']
    search_fields = ['user__username', 'user__email']
    readonly_fields = [
        'created_at', 'updated_at', 'last_activity',
        'balance_hash', 'available_btc', 'available_xmr'
    ]
    
    fieldsets = (
        ('User Information', {
            'fields': ('user',)
        }),
        ('Balances', {
            'fields': (
                'balance_btc', 'balance_xmr',
                'escrow_btc', 'escrow_xmr',
                'available_btc', 'available_xmr'
            )
        }),
        ('Security Settings', {
            'fields': (
                'withdrawal_pin', 'two_fa_enabled', 'two_fa_secret',
                'daily_withdrawal_limit_btc', 'daily_withdrawal_limit_xmr'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_activity')
        }),
        ('Integrity', {
            'fields': ('balance_hash',)
        })
    )
    
    def balance_btc_display(self, obj):
        return f"{obj.balance_btc:.8f} BTC"
    balance_btc_display.short_description = "BTC Balance"
    
    def balance_xmr_display(self, obj):
        return f"{obj.balance_xmr:.12f} XMR"
    balance_xmr_display.short_description = "XMR Balance"
    
    def escrow_btc_display(self, obj):
        return f"{obj.escrow_btc:.8f} BTC"
    escrow_btc_display.short_description = "BTC Escrow"
    
    def escrow_xmr_display(self, obj):
        return f"{obj.escrow_xmr:.12f} XMR"
    escrow_xmr_display.short_description = "XMR Escrow"
    
    def available_btc(self, obj):
        return f"{obj.get_available_balance('btc'):.8f} BTC"
    available_btc.short_description = "Available BTC"
    
    def available_xmr(self, obj):
        return f"{obj.get_available_balance('xmr'):.12f} XMR"
    available_xmr.short_description = "Available XMR"
    
    def balance_hash(self, obj):
        return obj.generate_balance_hash()[:16] + "..."
    balance_hash.short_description = "Balance Hash"


@admin.register(WithdrawalRequest)
class WithdrawalRequestAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'amount_display', 'currency', 'status_display',
        'risk_score_display', 'created_at', 'processed_by'
    ]
    list_filter = [
        'status', 'currency', 'manual_review_required',
        'two_fa_verified', 'pin_verified', 'created_at'
    ]
    search_fields = ['user__username', 'address', 'tx_hash']
    readonly_fields = [
        'created_at', 'updated_at', 'risk_score', 'risk_factors',
        'manual_review_required'
    ]
    
    fieldsets = (
        ('Request Information', {
            'fields': ('user', 'amount', 'currency', 'address')
        }),
        ('Status', {
            'fields': ('status', 'processed_by', 'processed_at')
        }),
        ('Transaction Details', {
            'fields': ('tx_hash', 'tx_fee')
        }),
        ('Security Verification', {
            'fields': ('two_fa_verified', 'pin_verified')
        }),
        ('Risk Assessment', {
            'fields': ('risk_score', 'risk_factors', 'manual_review_required')
        }),
        ('Notes', {
            'fields': ('user_note', 'admin_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )
    
    actions = ['approve_withdrawal', 'reject_withdrawal', 'mark_completed']
    
    def amount_display(self, obj):
        if obj.currency == 'btc':
            return f"{obj.amount:.8f} BTC"
        else:
            return f"{obj.amount:.12f} XMR"
    amount_display.short_description = "Amount"
    
    def status_display(self, obj):
        colors = {
            'pending': '#ffa500',
            'reviewing': '#0066cc',
            'approved': '#28a745',
            'processing': '#17a2b8',
            'completed': '#28a745',
            'rejected': '#dc3545',
            'cancelled': '#6c757d'
        }
        color = colors.get(obj.status, '#000')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_display.short_description = "Status"
    
    def risk_score_display(self, obj):
        if obj.risk_score >= 40:
            color = '#dc3545'  # Red
        elif obj.risk_score >= 20:
            color = '#ffa500'  # Orange
        else:
            color = '#28a745'  # Green
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.risk_score
        )
    risk_score_display.short_description = "Risk Score"
    
    def approve_withdrawal(self, request, queryset):
        """Approve withdrawal requests and deduct from wallet balance"""
        approved_count = 0
        
        for withdrawal in queryset.filter(status='pending'):
            try:
                with transaction.atomic():
                    wallet = Wallet.objects.select_for_update().get(user=withdrawal.user)
                    
                    can_withdraw, message = wallet.can_withdraw(withdrawal.currency, withdrawal.amount)
                    if not can_withdraw:
                        messages.error(request, f"Cannot approve withdrawal for {withdrawal.user.username}: {message}")
                        continue
                    
                    if withdrawal.currency == 'btc':
                        wallet.balance_btc -= withdrawal.amount
                    else:
                        wallet.balance_xmr -= withdrawal.amount
                    
                    wallet.save()
                    
                    withdrawal.status = 'approved'
                    withdrawal.processed_by = request.user
                    withdrawal.processed_at = timezone.now()
                    withdrawal.save()
                    
                    AuditLog.objects.create(
                        user=withdrawal.user,
                        action='withdrawal_approved',
                        details={
                            'withdrawal_id': str(withdrawal.id),
                            'amount': str(withdrawal.amount),
                            'currency': withdrawal.currency,
                            'admin': request.user.username
                        }
                    )
                    
                    approved_count += 1
                    
            except Exception as e:
                messages.error(request, f"Error approving withdrawal for {withdrawal.user.username}: {str(e)}")
        
        if approved_count > 0:
            messages.success(request, f"Approved {approved_count} withdrawal(s). Balances have been deducted.")
    
    approve_withdrawal.short_description = "Approve selected withdrawals (deduct balance)"
    
    def reject_withdrawal(self, request, queryset):
        """Reject withdrawal requests"""
        rejected_count = 0
        
        for withdrawal in queryset.filter(status__in=['pending', 'reviewing']):
            withdrawal.status = 'rejected'
            withdrawal.processed_by = request.user
            withdrawal.processed_at = timezone.now()
            withdrawal.save()
            
            AuditLog.objects.create(
                user=withdrawal.user,
                action='withdrawal_rejected',
                details={
                    'withdrawal_id': str(withdrawal.id),
                    'amount': str(withdrawal.amount),
                    'currency': withdrawal.currency,
                    'admin': request.user.username
                }
            )
            
            rejected_count += 1
        
        if rejected_count > 0:
            messages.success(request, f"Rejected {rejected_count} withdrawal(s).")
    
    reject_withdrawal.short_description = "Reject selected withdrawals"
    
    def mark_completed(self, request, queryset):
        """Mark approved withdrawals as completed after manual sending"""
        completed_count = 0
        
        for withdrawal in queryset.filter(status='approved'):
            withdrawal.status = 'completed'
            withdrawal.save()
            
            AuditLog.objects.create(
                user=withdrawal.user,
                action='withdrawal_completed',
                details={
                    'withdrawal_id': str(withdrawal.id),
                    'amount': str(withdrawal.amount),
                    'currency': withdrawal.currency,
                    'admin': request.user.username
                }
            )
            
            completed_count += 1
        
        if completed_count > 0:
            messages.success(request, f"Marked {completed_count} withdrawal(s) as completed.")
    
    mark_completed.short_description = "Mark as completed (after manual sending)"


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'type', 'amount_display', 'currency',
        'balance_after_display', 'created_at'
    ]
    list_filter = ['type', 'currency', 'created_at']
    search_fields = ['user__username', 'reference', 'transaction_hash']
    readonly_fields = [
        'transaction_hash', 'created_at', 'balance_before', 'balance_after'
    ]
    
    fieldsets = (
        ('Transaction Information', {
            'fields': ('user', 'type', 'amount', 'currency')
        }),
        ('Conversion Details', {
            'fields': ('converted_amount', 'converted_currency', 'conversion_rate')
        }),
        ('Balance Tracking', {
            'fields': ('balance_before', 'balance_after')
        }),
        ('Reference & Security', {
            'fields': ('reference', 'transaction_hash')
        }),
        ('Metadata', {
            'fields': ('metadata',)
        }),
        ('Timestamps', {
            'fields': ('created_at',)
        })
    )
    
    def amount_display(self, obj):
        if obj.currency == 'btc':
            return f"{obj.amount:.8f}"
        else:
            return f"{obj.amount:.12f}"
    amount_display.short_description = "Amount"
    
    def balance_after_display(self, obj):
        if obj.currency == 'btc':
            return f"{obj.balance_after:.8f}"
        else:
            return f"{obj.balance_after:.12f}"
    balance_after_display.short_description = "Balance After"


@admin.register(ConversionRate)
class ConversionRateAdmin(admin.ModelAdmin):
    list_display = [
        'from_currency', 'to_currency', 'rate_display',
        'is_active', 'valid_from', 'valid_until'
    ]
    list_filter = ['is_active', 'from_currency', 'to_currency', 'created_at']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Rate Information', {
            'fields': ('from_currency', 'to_currency', 'rate')
        }),
        ('Validity', {
            'fields': ('is_active', 'valid_from', 'valid_until')
        }),
        ('Source', {
            'fields': ('source', 'source_data')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        })
    )
    
    def rate_display(self, obj):
        return f"1 {obj.from_currency.upper()} = {obj.rate:.6f} {obj.to_currency.upper()}"
    rate_display.short_description = "Exchange Rate"


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'action', 'risk_score_display',
        'flagged_display', 'created_at'
    ]
    list_filter = ['action', 'flagged', 'created_at']
    search_fields = ['user__username']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Log Information', {
            'fields': ('user', 'action', 'details')
        }),
        ('Security Assessment', {
            'fields': ('risk_score', 'flagged')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        })
    )
    
    def risk_score_display(self, obj):
        if obj.risk_score >= 70:
            color = '#dc3545'  # Red
        elif obj.risk_score >= 40:
            color = '#ffa500'  # Orange
        else:
            color = '#28a745'  # Green
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.risk_score
        )
    risk_score_display.short_description = "Risk Score"
    
    def flagged_display(self, obj):
        if obj.flagged:
            return format_html('<span style="color: #dc3545; font-weight: bold;">🚩 FLAGGED</span>')
        return format_html('<span style="color: #28a745;">✓ Normal</span>')
    flagged_display.short_description = "Status"


@admin.register(WalletBalanceCheck)
class WalletBalanceCheckAdmin(admin.ModelAdmin):
    list_display = [
        'wallet', 'discrepancy_found_display', 'resolved',
        'checked_at', 'resolved_by'
    ]
    list_filter = ['discrepancy_found', 'resolved', 'checked_at']
    search_fields = ['wallet__user__username']
    readonly_fields = ['checked_at', 'resolved_at']
    
    fieldsets = (
        ('Check Information', {
            'fields': ('wallet',)
        }),
        ('Expected Balances', {
            'fields': ('expected_btc', 'expected_xmr', 'expected_escrow_btc', 'expected_escrow_xmr')
        }),
        ('Actual Balances', {
            'fields': ('actual_btc', 'actual_xmr', 'actual_escrow_btc', 'actual_escrow_xmr')
        }),
        ('Results', {
            'fields': ('discrepancy_found', 'discrepancy_details')
        }),
        ('Resolution', {
            'fields': ('resolved', 'resolved_by', 'resolution_notes', 'resolved_at')
        }),
        ('Timestamps', {
            'fields': ('checked_at',)
        })
    )
    
    def discrepancy_found_display(self, obj):
        if obj.discrepancy_found:
            return format_html('<span style="color: #dc3545; font-weight: bold;">⚠️ DISCREPANCY</span>')
        return format_html('<span style="color: #28a745;">✓ OK</span>')
    discrepancy_found_display.short_description = "Status"
