from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
import time


class SecondaryAuthForm(forms.Form):
    """Secondary password authentication form for admin panel"""
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter secondary password',
            'autocomplete': 'off'
        }),
        label='Secondary Password',
        help_text='Enter the admin panel secondary password'
    )


class AdminPGPChallengeForm(forms.Form):
    """PGP challenge verification form for admin panel"""
    signed_challenge = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 10,
            'placeholder': 'Paste your signed PGP challenge response here...',
            'style': 'font-family: monospace; font-size: 12px;'
        }),
        label='Signed Challenge Response',
        help_text='Sign the challenge with your PGP key and paste the signed message here'
    )


class AdminLoginForm(AuthenticationForm):
    """Enhanced admin login form"""
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Admin Username',
            'autocomplete': 'username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password',
            'autocomplete': 'current-password'
        })
    )


class AdminTripleAuthForm(forms.Form):
    """Complete triple authentication form for admin access"""
    
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Admin Username'
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Primary Password'
        })
    )
    
    secondary_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Secondary Password'
        })
    )
    
    pgp_challenge_response = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Decrypted PGP challenge response'
        }),
        help_text='Decrypt the PGP challenge and paste the result here'
    )
    
    challenge_id = forms.CharField(widget=forms.HiddenInput(), required=False)
    challenge_timestamp = forms.CharField(widget=forms.HiddenInput(), required=False)
    
    def __init__(self, *args, **kwargs):
        self.expected_challenge = kwargs.pop('expected_challenge', None)
        self.challenge_id = kwargs.pop('challenge_id', None)
        super().__init__(*args, **kwargs)
        
        if self.challenge_id:
            self.fields['challenge_id'].initial = self.challenge_id
        self.fields['challenge_timestamp'].initial = str(int(time.time()))
    
    def clean_username(self):
        """Validate admin user exists and is superuser"""
        username = self.cleaned_data.get('username')
        try:
            user = User.objects.get(username=username)
            if not user.is_superuser:
                raise ValidationError('Invalid admin credentials')
            return username
        except User.DoesNotExist:
            raise ValidationError('Invalid admin credentials')
    
    def clean_pgp_challenge_response(self):
        """Validate PGP challenge response"""
        response = self.cleaned_data.get('pgp_challenge_response', '').strip()
        
        if not response:
            raise ValidationError('PGP challenge response is required')
        
        if self.expected_challenge and response != self.expected_challenge:
            raise ValidationError('Invalid PGP challenge response')
        
        return response
    
    def clean_challenge_timestamp(self):
        """Validate challenge hasn't expired"""
        timestamp = self.cleaned_data.get('challenge_timestamp')
        
        if timestamp:
            try:
                challenge_time = int(timestamp)
                current_time = int(time.time())
                
                if current_time - challenge_time > 600:
                    raise ValidationError('Challenge has expired')
                    
            except (ValueError, TypeError):
                raise ValidationError('Invalid challenge timestamp')
        
        return timestamp
