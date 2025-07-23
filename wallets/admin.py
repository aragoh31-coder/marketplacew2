from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.contrib import messages
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.shortcuts import redirect
from functools import wraps
from decimal import Decimal
import logging
from .models import (
    Wallet, WithdrawalRequest, Transaction, 
    ConversionRate, AuditLog, WalletBalanceCheck
)

logger = logging.getLogger('wallet.admin')


def require_2fa(view_func):
    """Decorator to require 2FA for sensitive operations"""
    @wraps(view_func)
    def wrapped_view(self, request, *args, **kwargs):
        cache_key = f'2fa_verified:{request.user.id}'
        if not cache.get(cache_key):
            messages.error(request, "Please verify 2FA before performing this action")
            return redirect(request.META.get('HTTP_REFERER', '/admin/'))
        
        return view_func(self, request, *args, **kwargs)
    return wrapped_view


def log_admin_action(request, action, obj, details):
    """Comprehensive logging for admin actions"""
    logger.info(f"Admin action: {action}", extra={
        'user': request.user.username,
        'user_id': request.user.id,
        'object': str(obj),
        'object_id': obj.pk if obj else None,
        'details': details
    })
    
    AuditLog.objects.create(
        user=request.user,
        action='admin_action',
        details={
            'action': action,
            'object_type': obj.__class__.__name__ if obj else None,
            'object_id': obj.pk if obj else None,
            'details': details
        }
    )


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'balance_btc_display', 'balance_xmr_display',
        'escrow_btc_display', 'escrow_xmr_display', 'risk_indicator', 'last_activity'
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
        available = obj.get_available_balance('btc')
        return format_html(
            '<strong>{}</strong> BTC<br><small>Available: {}</small>',
            obj.balance_btc, available
        )
    balance_btc_display.short_description = 'BTC Balance'
    
    def balance_xmr_display(self, obj):
        available = obj.get_available_balance('xmr')
        return format_html(
            '<strong>{}</strong> XMR<br><small>Available: {}</small>',
            obj.balance_xmr, available
        )
    balance_xmr_display.short_description = 'XMR Balance'
    
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
    
    def risk_indicator(self, obj):
        recent_logs = AuditLog.objects.filter(
            user=obj.user,
            flagged=True,
            created_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).count()
        
        if recent_logs > 0:
            return format_html(
                '<span style="color: red;">⚠️ {} alerts</span>',
                recent_logs
            )
        return format_html('<span style="color: green;">✓ OK</span>')
    risk_indicator.short_description = 'Risk Status'


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
    
    actions = ['approve_withdrawal', 'reject_withdrawal', 'mark_completed', 'flag_for_review']
    
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
        if obj.risk_score >= 60:
            color = '#dc3545'
            icon = '🚨'
        elif obj.risk_score >= 40:
            color = '#ffa500'
            icon = '⚠️'
        elif obj.risk_score >= 20:
            color = '#ffcc00'
            icon = '⚡'
        else:
            color = '#28a745'
            icon = '✓'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color, icon, obj.risk_score
        )
    risk_score_display.short_description = "Risk Score"
    
    @method_decorator(require_2fa)
    def approve_withdrawal(self, request, queryset):
        """Approve withdrawal requests and deduct from wallet balance"""
        approved_count = 0
        error_count = 0
        
        for withdrawal in queryset.filter(status='pending'):
            try:
                with transaction.atomic():
                    wallet = Wallet.objects.select_for_update().get(user=withdrawal.user)
                    withdrawal = WithdrawalRequest.objects.select_for_update().get(pk=withdrawal.pk)
                    
                    if withdrawal.status != 'pending':
                        continue
                    
                    can_withdraw, reason = wallet.can_withdraw(withdrawal.currency, withdrawal.amount)
                    if not can_withdraw:
                        messages.error(
                            request, 
                            f"Cannot approve withdrawal {withdrawal.id}: {reason}"
                        )
                        error_count += 1
                        continue
                    
                    balance_field = f'balance_{withdrawal.currency}'
                    balance_before = getattr(wallet, balance_field)
                    
                    new_balance = balance_before - withdrawal.amount
                    setattr(wallet, balance_field, new_balance)
                    wallet.save()
                    
                    withdrawal.status = 'approved'
                    withdrawal.processed_by = request.user
                    withdrawal.processed_at = timezone.now()
                    withdrawal.admin_notes = f"Approved by {request.user.username} at {timezone.now()}"
                    withdrawal.save()
                    
                    log_admin_action(
                        request,
                        'withdrawal_approved',
                        withdrawal,
                        {
                            'amount': str(withdrawal.amount),
                            'currency': withdrawal.currency,
                            'balance_before': str(balance_before),
                            'balance_after': str(new_balance)
                        }
                    )
                    
                    approved_count += 1
                    
            except Exception as e:
                logger.error(f"Error approving withdrawal {withdrawal.id}: {str(e)}")
                messages.error(
                    request, 
                    f"Error processing withdrawal {withdrawal.id}: {str(e)}"
                )
                error_count += 1
        
        if approved_count:
            messages.success(
                request, 
                f"Successfully approved {approved_count} withdrawals"
            )
        if error_count:
            messages.error(
                request, 
                f"Failed to process {error_count} withdrawals"
            )
    
    approve_withdrawal.short_description = "Approve selected withdrawals (requires 2FA)"
    
    @method_decorator(require_2fa)
    def reject_withdrawal(self, request, queryset):
        """Reject withdrawal requests"""
        rejected_count = 0
        
        for withdrawal in queryset.filter(status__in=['pending', 'reviewing']):
            withdrawal.status = 'rejected'
            withdrawal.processed_by = request.user
            withdrawal.processed_at = timezone.now()
            withdrawal.admin_notes = f"Rejected by {request.user.username} at {timezone.now()}"
            withdrawal.save()
            
            log_admin_action(
                request,
                'withdrawal_rejected',
                withdrawal,
                {
                    'amount': str(withdrawal.amount),
                    'currency': withdrawal.currency,
                    'reason': 'Manual rejection'
                }
            )
            
            rejected_count += 1
        
        if rejected_count > 0:
            messages.success(request, f"Rejected {rejected_count} withdrawal(s).")
    
    reject_withdrawal.short_description = "Reject selected withdrawals (requires 2FA)"
    
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
    
    def flag_for_review(self, request, queryset):
        """Flag withdrawals for manual review"""
        flagged_count = 0
        
        for withdrawal in queryset.filter(status='pending'):
            withdrawal.status = 'reviewing'
            withdrawal.manual_review_required = True
            withdrawal.admin_notes = f"Flagged for review by {request.user.username} at {timezone.now()}"
            withdrawal.save()
            
            log_admin_action(
                request,
                'withdrawal_flagged',
                withdrawal,
                {
                    'amount': str(withdrawal.amount),
                    'currency': withdrawal.currency,
                    'reason': 'Manual flag for review'
                }
            )
            
            flagged_count += 1
        
        if flagged_count > 0:
            messages.success(request, f"Flagged {flagged_count} withdrawal(s) for review.")
    
    flag_for_review.short_description = "Flag for manual review"


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
