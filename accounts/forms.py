import shutil
import tempfile

import gnupg
from django import forms
from django.core.exceptions import ValidationError

from .models import User


class DeleteAccountForm(forms.Form):
    """Form for account deletion confirmation"""

    password = forms.CharField(
        widget=forms.PasswordInput(), label="Confirm your password to delete account"
    )


class HoneypotMixin(forms.Form):
    honeypot = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean_honeypot(self):
        if self.cleaned_data.get("honeypot"):
            raise ValidationError("Bot detected")


class LoginForm(HoneypotMixin):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput())


class RegistrationForm(HoneypotMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["username", "password"]

    password = forms.CharField(widget=forms.PasswordInput())


class PGPKeyForm(forms.ModelForm):
    """
    Form for uploading and enabling a PGP public key for login 2FA.
    """

    enable_pgp_login = forms.BooleanField(required=False, label="Enable PGP Login")

    class Meta:
        model = User
        fields = ["pgp_public_key"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, "pgp_login_enabled"):
            self.fields["enable_pgp_login"].initial = self.instance.pgp_login_enabled

    def clean_pgp_public_key(self):
        key_data = self.cleaned_data.get("pgp_public_key", "").strip()
        if not key_data.startswith("-----BEGIN PGP PUBLIC KEY BLOCK-----"):
            raise ValidationError("Invalid PGP public key format.")
        tempdir = tempfile.mkdtemp()
        try:
            gpg = gnupg.GPG(gnupghome=tempdir)
            result = gpg.import_keys(key_data)
        finally:
            shutil.rmtree(tempdir, ignore_errors=True)
        if not result or not result.fingerprints:
            raise ValidationError("Could not import PGP key; please verify it's valid.")
        self.cleaned_data["pgp_fingerprint"] = result.fingerprints[0]
        return key_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.pgp_fingerprint = self.cleaned_data.get("pgp_fingerprint")
        user.pgp_login_enabled = self.cleaned_data.get("enable_pgp_login", False)
        if commit:
            user.save(
                update_fields=["pgp_public_key", "pgp_fingerprint", "pgp_login_enabled"]
            )
        return user
