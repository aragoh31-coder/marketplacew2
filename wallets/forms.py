from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
import re


class WithdrawalForm(forms.Form):
    """Secure withdrawal form with validation"""
    CURRENCY_CHOICES = [
        ('btc', 'Bitcoin (BTC)'),
        ('xmr', 'Monero (XMR)'),
    ]
    
    currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    amount = forms.DecimalField(
        max_digits=16,
        decimal_places=12,
        min_value=Decimal('0.000000000001'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.000000000001'
        })
    )
    
    address = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Cryptocurrency address'
        })
    )
    
    two_fa_code = forms.CharField(
        max_length=6,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '6-digit code',
            'autocomplete': 'off'
        })
    )
    
    pin = forms.CharField(
        max_length=6,
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Withdrawal PIN',
            'autocomplete': 'off'
        })
    )
    
    note = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional note'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user:
            wallet = self.user.wallet
            if wallet.two_fa_enabled:
                self.fields['two_fa_code'].required = True
            if wallet.withdrawal_pin:
                self.fields['pin'].required = True
    
    def clean_address(self):
        """Validate cryptocurrency address format"""
        address = self.cleaned_data['address']
        currency = self.data.get('currency')
        
        if currency == 'btc':
            if not re.match(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$|^bc1[a-z0-9]{39,59}$', address):
                raise ValidationError("Invalid Bitcoin address format")
        elif currency == 'xmr':
            if not re.match(r'^4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}$', address):
                raise ValidationError("Invalid Monero address format")
        
        return address
    
    def clean_amount(self):
        """Validate withdrawal amount"""
        amount = self.cleaned_data['amount']
        currency = self.data.get('currency')
        
        if not self.user:
            return amount
        
        wallet = self.user.wallet
        available = wallet.get_available_balance(currency)
        
        if amount > available:
            raise ValidationError(
                f"Insufficient balance. Available: {available} {currency.upper()}"
            )
        
        daily_total = wallet.get_daily_withdrawal_total(currency)
        limit = getattr(wallet, f'daily_withdrawal_limit_{currency}')
        
        if daily_total + amount > limit:
            remaining = limit - daily_total
            raise ValidationError(
                f"Daily limit exceeded. Remaining today: {remaining} {currency.upper()}"
            )
        
        return amount


class ConversionForm(forms.Form):
    """Currency conversion form"""
    CURRENCY_CHOICES = [
        ('btc', 'Bitcoin (BTC)'),
        ('xmr', 'Monero (XMR)'),
    ]
    
    from_currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    to_currency = forms.ChoiceField(
        choices=CURRENCY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    amount = forms.DecimalField(
        max_digits=16,
        decimal_places=12,
        min_value=Decimal('0.000000000001'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.000000000001'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        from_currency = cleaned_data.get('from_currency')
        to_currency = cleaned_data.get('to_currency')
        amount = cleaned_data.get('amount')
        
        if from_currency == to_currency:
            raise ValidationError("Cannot convert to the same currency")
        
        if self.user and amount:
            wallet = self.user.wallet
            available = wallet.get_available_balance(from_currency)
            
            if amount > available:
                raise ValidationError(
                    f"Insufficient {from_currency.upper()} balance. Available: {available}"
                )
        
        return cleaned_data


class TwoFactorForm(forms.Form):
    """2FA verification form"""
    code = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '6-digit code',
            'autocomplete': 'off'
        })
    )


class WithdrawalPinForm(forms.Form):
    """Withdrawal PIN form"""
    pin = forms.CharField(
        max_length=6,
        min_length=4,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter PIN',
            'autocomplete': 'off'
        })
    )


class SecuritySettingsForm(forms.Form):
    """Security settings form"""
    enable_2fa = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    new_pin = forms.CharField(
        max_length=6,
        min_length=4,
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'New PIN (4-6 digits)',
            'autocomplete': 'off'
        })
    )
    
    confirm_pin = forms.CharField(
        max_length=6,
        min_length=4,
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm PIN',
            'autocomplete': 'off'
        })
    )
    
    daily_withdrawal_limit_btc = forms.DecimalField(
        max_digits=16,
        decimal_places=8,
        min_value=Decimal('0.00000001'),
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.00000001'
        })
    )
    
    daily_withdrawal_limit_xmr = forms.DecimalField(
        max_digits=16,
        decimal_places=12,
        min_value=Decimal('0.000000000001'),
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.000000000001'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        new_pin = cleaned_data.get('new_pin')
        confirm_pin = cleaned_data.get('confirm_pin')
        
        if new_pin and new_pin != confirm_pin:
            raise ValidationError("PIN confirmation does not match")
        
        if new_pin and not new_pin.isdigit():
            raise ValidationError("PIN must contain only digits")
        
        return cleaned_data
