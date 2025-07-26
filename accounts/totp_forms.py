from django import forms
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError

class TOTPSetupForm(forms.Form):
    """Form for TOTP setup verification"""
    totp_token = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': '000000',
            'autocomplete': 'off',
            'inputmode': 'numeric',
            'pattern': '[0-9]*'
        }),
        help_text="Enter the 6-digit code from your authenticator app"
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_totp_token(self):
        token = self.cleaned_data['totp_token']
        
        if not token.isdigit():
            raise ValidationError("Token must contain only numbers")
        
        if not self.user.verify_totp(token):
            raise ValidationError("Invalid token. Please check your authenticator app and try again.")
        
        return token

class TOTPVerificationForm(forms.Form):
    """Form for TOTP verification during login"""
    totp_token = forms.CharField(
        max_length=8,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': '000000',
            'autocomplete': 'off',
            'inputmode': 'numeric'
        }),
        help_text="Enter your 6-digit authenticator code or 8-character backup code"
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_totp_token(self):
        token = self.cleaned_data['totp_token'].strip().upper()
        
        if len(token) == 6 and token.isdigit():
            if self.user.verify_totp(token):
                return token
            else:
                raise ValidationError("Invalid authenticator code")
        
        elif len(token) == 8:
            if self.user.verify_backup_code(token):
                return token
            else:
                raise ValidationError("Invalid backup code")
        
        else:
            raise ValidationError("Enter a 6-digit authenticator code or 8-character backup code")

class TOTPDisableForm(forms.Form):
    """Form for disabling TOTP"""
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password to confirm'
        }),
        help_text="Enter your account password to disable 2FA"
    )
    
    totp_token = forms.CharField(
        max_length=8,
        widget=forms.TextInput(attrs={
            'class': 'form-control text-center',
            'placeholder': '000000',
            'autocomplete': 'off',
            'inputmode': 'numeric'
        }),
        help_text="Enter your current authenticator code or backup code"
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_password(self):
        password = self.cleaned_data['password']
        
        if not self.user.check_password(password):
            raise ValidationError("Incorrect password")
        
        return password
    
    def clean_totp_token(self):
        token = self.cleaned_data['totp_token'].strip().upper()
        
        if len(token) == 6 and token.isdigit():
            if self.user.verify_totp(token):
                return token
        
        elif len(token) == 8:
            if self.user.verify_backup_code(token):
                return token
        
        raise ValidationError("Invalid authenticator code or backup code")

class BackupCodesRegenerateForm(forms.Form):
    """Form for regenerating backup codes"""
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password to confirm'
        }),
        help_text="Enter your account password to generate new backup codes"
    )
    
    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
    
    def clean_password(self):
        password = self.cleaned_data['password']
        
        if not self.user.check_password(password):
            raise ValidationError("Incorrect password")
        
        return password
