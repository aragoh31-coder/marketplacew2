from django.db import models, transaction
from decimal import Decimal


class Wallet(models.Model):
    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))


class WithdrawalRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected')
    )
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=18, decimal_places=8)
    address = models.CharField(max_length=256)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey('accounts.User', null=True, blank=True, related_name='approved_withdrawals', on_delete=models.SET_NULL)
