from django import forms
from django.contrib.auth.forms import PasswordChangeForm

from .models import User


class UserProfileForm(forms.ModelForm):
    """Form for updating a user's profile settings."""
    class Meta:
        model = User
        fields = ['default_currency', 'default_shipping_country']
        widgets = {
            'default_currency': forms.Select(attrs={'class': 'form-control'}),
            'default_shipping_country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., United States, Germany, etc.'
            }),
        }


class PGPKeyForm(forms.Form):
    """
    Form for handling PGP public key submissions.

    - Allows users to submit a PGP public key.
    - Validates the key's format and cryptographic properties (e.g., not expired,
      not revoked, capable of encryption).
    - Stores the validated key and its fingerprint in the session for verification.
    - Allows enabling/disabling PGP-based 2FA for login.
    """
    pgp_public_key = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 10,
            'placeholder': '-----BEGIN PGP PUBLIC KEY BLOCK-----\n...\n-----END PGP PUBLIC KEY BLOCK-----'
        }),
        required=False
    )
    enable_pgp_login = forms.BooleanField(
        required=False,
        label="Enable PGP-based login challenge",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def clean_pgp_public_key(self):
        key = self.cleaned_data.get('pgp_public_key')
        if key:
            key = key.strip()
            
            from .pgp_service import PGPService
            pgp_service = PGPService()
            
            validation_result = pgp_service.validate_key_format(key)
            if not validation_result['success']:
                error = validation_result['error']
                if 'BEGIN and END markers' in error:
                    raise forms.ValidationError("Invalid key format. Please ensure you're copying the entire key including the -----BEGIN PGP PUBLIC KEY BLOCK----- and -----END PGP PUBLIC KEY BLOCK----- lines.")
                else:
                    raise forms.ValidationError(f"Invalid key format: {error}")
            
            import_result = pgp_service.import_public_key(key)
            
            if not import_result['success']:
                error = import_result['error']
                if 'expired' in error.lower():
                    raise forms.ValidationError("This PGP key has expired. Please use a valid, non-expired key.")
                elif 'revoked' in error.lower():
                    raise forms.ValidationError("This PGP key has been revoked. Please use a valid key.")
                elif 'encryption' in error.lower():
                    raise forms.ValidationError("This key doesn't support encryption. Please use a key with encryption capability.")
                elif 'invalid' in error.lower() or 'format' in error.lower():
                    raise forms.ValidationError("Invalid key format or corrupted key data. Please check your key and try again.")
                else:
                    raise forms.ValidationError(f"Key validation failed: {error}")
            
            caps = import_result.get('capabilities', {})
            if not caps.get('can_encrypt') and not caps.get('has_encryption_subkey'):
                raise forms.ValidationError("This key doesn't support encryption. Please use a key with encryption capability.")
            
            if caps.get('is_expired'):
                raise forms.ValidationError("This PGP key has expired. Please use a valid, non-expired key.")
            
            if caps.get('is_revoked'):
                raise forms.ValidationError("This PGP key has been revoked. Please use a valid key.")
            
            self.fingerprint = import_result['fingerprint']
            self.key_info = pgp_service.get_key_info(import_result['fingerprint'])
            
        return key


class CustomPasswordChangeForm(PasswordChangeForm):
    """
    A custom password change form that applies specific styling to the fields.
    Inherits from Django's built-in PasswordChangeForm and overrides the widgets.
    """
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Current password'
        })
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'New password'
        })
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new password'
        })
    )




class DeleteAccountForm(forms.Form):
    """
    A form for account deletion that requires the user to type 'DELETE'
    and enter their password to confirm the action.
    """
    confirm_delete = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Type DELETE to confirm'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your password'
        })
    )
    
    def clean_confirm_delete(self):
        confirm = self.cleaned_data.get('confirm_delete')
        if confirm != 'DELETE':
            raise forms.ValidationError('Please type DELETE to confirm')
        return confirm
