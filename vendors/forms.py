from django import forms
from django.utils import timezone
from datetime import datetime, timedelta
from .models import Vendor, SubVendor
from django.contrib.auth import get_user_model
from products.models import Product
from core.security.image_security import SecureImageProcessor

User = get_user_model()

class VendorApplicationForm(forms.ModelForm):
    terms_accepted = forms.BooleanField(
        required=True,
        label='I accept the vendor terms and conditions'
    )
    
    class Meta:
        model = Vendor
        fields = ['description']
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Describe your business and what you plan to sell...',
                'class': 'form-input'
            }),
        }

class ProductForm(forms.ModelForm):
    image = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'accept': 'image/jpeg,image/png,image/gif,image/bmp,image/webp',
            'class': 'form-input'
        }),
        help_text='Max 2MB. JPEG, PNG, GIF, BMP, or WebP (all converted to JPEG).'
    )
    
    class Meta:
        model = Product
        fields = [
            'name', 'description', 'category', 
            'price_btc', 'price_xmr', 'stock_quantity'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={
                'rows': 10,
                'class': 'form-input'
            }),
            'category': forms.Select(attrs={'class': 'form-input'}),
            'price_btc': forms.NumberInput(attrs={
                'step': '0.00000001',
                'min': '0',
                'class': 'form-input',
                'placeholder': 'Price in BTC'
            }),
            'price_xmr': forms.NumberInput(attrs={
                'step': '0.0001',
                'min': '0',
                'class': 'form-input',
                'placeholder': 'Price in XMR'
            }),
            'stock_quantity': forms.NumberInput(attrs={
                'min': '0',
                'class': 'form-input'
            }),
        }
    
    def clean_image(self):
        image = self.cleaned_data.get('image')
        
        if image:
            if image.size > 2 * 1024 * 1024:
                raise forms.ValidationError(
                    f"Image file too large. Maximum size is 2MB (your file: {image.size / 1024 / 1024:.1f}MB)"
                )
            
            name = image.name.lower()
            allowed = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
            if not any(name.endswith(ext) for ext in allowed):
                raise forms.ValidationError(
                    "Invalid file type. Supported formats: JPEG, PNG, GIF, BMP, WebP"
                )
        
        return image
    
    def save(self, commit=True, user=None):
        instance = super().save(commit=False)
        
        if user:
            from vendors.models import Vendor
            try:
                vendor = Vendor.objects.get(user=user)
                instance.vendor = vendor
            except Vendor.DoesNotExist:
                raise forms.ValidationError("User must be an approved vendor to create products")
        
        image = self.cleaned_data.get('image')
        if image and user:
            processor = SecureImageProcessor()
            success, filename, thumb_filename = processor.validate_and_process_image(
                image, user
            )
            
            if success:
                if instance.pk and (instance.image_filename or instance.thumbnail_filename):
                    processor.delete_images(
                        instance.image_filename, 
                        instance.thumbnail_filename
                    )
                
                instance.image_filename = filename
                instance.thumbnail_filename = thumb_filename
            else:
                self.add_error('image', filename)  # filename contains error message
                return None
        
        if commit:
            instance.save()
        
        return instance

class VendorSettingsForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ['description']
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 5,
                'class': 'form-input'
            }),
        }


class VacationModeForm(forms.Form):
    vacation_message = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'class': 'form-input',
            'placeholder': 'Message to display to customers (e.g., "On vacation until Dec 25. Orders will be processed after I return.")'
        }),
        required=False,
        label='Vacation Message'
    )
    
    vacation_ends = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-input',
            'min': timezone.now().strftime('%Y-%m-%dT%H:%M'),
        }),
        required=False,
        label='Vacation Ends (Optional)'
    )
    
    def clean_vacation_ends(self):
        ends = self.cleaned_data.get('vacation_ends')
        if ends and ends < timezone.now():
            raise forms.ValidationError('End date must be in the future.')
        return ends


class SubVendorForm(forms.ModelForm):
    username = forms.CharField(
        max_length=30,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'support1'
        }),
        help_text='Will be prefixed with your vendor name'
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
        }),
        help_text='Strong password for sub-vendor account'
    )
    
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
        })
    )
    
    daily_message_limit = forms.IntegerField(
        min_value=10,
        max_value=500,
        initial=100,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
        })
    )
    
    class Meta:
        model = SubVendor
        fields = [
            'can_view_orders', 
            'can_respond_messages',
            'can_update_tracking',
            'can_process_refunds',
            'daily_message_limit'
        ]
        widgets = {
            'can_view_orders': forms.CheckboxInput(attrs={'class': 'form-check'}),
            'can_respond_messages': forms.CheckboxInput(attrs={'class': 'form-check'}),
            'can_update_tracking': forms.CheckboxInput(attrs={'class': 'form-check'}),
            'can_process_refunds': forms.CheckboxInput(attrs={'class': 'form-check'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.editing = kwargs.pop('editing', False)
        super().__init__(*args, **kwargs)
        
        if self.editing:
            del self.fields['username']
            del self.fields['password']
            del self.fields['confirm_password']
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            if len(username) < 3:
                raise forms.ValidationError('Username must be at least 3 characters.')
            if not username.replace('_', '').isalnum():
                raise forms.ValidationError('Username can only contain letters, numbers, and underscores.')
        return username
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not self.editing:
            password = cleaned_data.get('password')
            confirm = cleaned_data.get('confirm_password')
            
            if password and confirm and password != confirm:
                raise forms.ValidationError('Passwords do not match.')
            
            if password and len(password) < 8:
                raise forms.ValidationError('Password must be at least 8 characters.')
        
        return cleaned_data
