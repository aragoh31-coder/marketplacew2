from django import forms
from django.core.exceptions import ValidationError
from .models import User

class HoneypotMixin(forms.Form):
    honeypot = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean_honeypot(self):
        if self.cleaned_data.get('honeypot'):
            raise ValidationError("Bot detected")

class LoginForm(HoneypotMixin):
    username = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput())

class RegistrationForm(HoneypotMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'password']
    password = forms.CharField(widget=forms.PasswordInput())
