from django import forms
from django.core.exceptions import ValidationError
from .models import Dispute, DisputeMessage, DisputeEvidence

class RaiseDisputeForm(forms.ModelForm):
    """Form for raising a new dispute"""
    
    class Meta:
        model = Dispute
        fields = ['dispute_type', 'title', 'description']
        widgets = {
            'dispute_type': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Brief summary of the issue',
                'maxlength': 255
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Provide detailed information about the issue...',
                'rows': 6
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['dispute_type'].empty_label = "Select dispute type"
        
        self.fields['title'].help_text = "Provide a clear, concise title for your dispute"
        self.fields['description'].help_text = "Include all relevant details, dates, and circumstances"
    
    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if len(title) < 10:
            raise ValidationError("Title must be at least 10 characters long")
        return title
    
    def clean_description(self):
        description = self.cleaned_data.get('description', '').strip()
        if len(description) < 50:
            raise ValidationError("Description must be at least 50 characters long")
        return description

class DisputeMessageForm(forms.ModelForm):
    """Form for adding messages to disputes"""
    
    class Meta:
        model = DisputeMessage
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Type your message here...',
                'rows': 4
            })
        }
    
    def clean_content(self):
        content = self.cleaned_data.get('content', '').strip()
        if len(content) < 10:
            raise ValidationError("Message must be at least 10 characters long")
        if len(content) > 2000:
            raise ValidationError("Message cannot exceed 2000 characters")
        return content

class DisputeEvidenceForm(forms.ModelForm):
    """Form for uploading evidence to disputes"""
    
    class Meta:
        model = DisputeEvidence
        fields = ['evidence_type', 'title', 'description', 'file']
        widgets = {
            'evidence_type': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Evidence title',
                'maxlength': 255
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Describe this evidence...',
                'rows': 3
            }),
            'file': forms.FileInput(attrs={
                'class': 'form-control-file',
                'accept': 'image/*,.pdf,.doc,.docx,.txt'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['evidence_type'].empty_label = "Select evidence type"
        
        self.fields['file'].help_text = "Supported formats: Images (JPG, PNG, GIF), PDF, DOC, TXT. Max size: 10MB"
        self.fields['title'].help_text = "Brief description of what this evidence shows"
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if file.size > 10 * 1024 * 1024:
                raise ValidationError("File size cannot exceed 10MB")
            
            allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.pdf', '.doc', '.docx', '.txt']
            file_extension = file.name.lower().split('.')[-1]
            if f'.{file_extension}' not in allowed_extensions:
                raise ValidationError("File type not supported")
        
        return file
    
    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if len(title) < 5:
            raise ValidationError("Title must be at least 5 characters long")
        return title

class AdminDisputeResolutionForm(forms.ModelForm):
    """Form for admin dispute resolution"""
    
    refund_amount = forms.DecimalField(
        max_digits=20,
        decimal_places=8,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '0.00000000',
            'step': '0.00000001'
        })
    )
    
    class Meta:
        model = Dispute
        fields = ['resolution_type', 'resolution_notes', 'admin_notes']
        widgets = {
            'resolution_type': forms.Select(attrs={
                'class': 'form-control',
                'required': True
            }),
            'resolution_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Explain the resolution to both parties...',
                'rows': 4
            }),
            'admin_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Internal admin notes (not visible to users)...',
                'rows': 3
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.dispute = kwargs.pop('dispute', None)
        super().__init__(*args, **kwargs)
        
        self.fields['resolution_type'].empty_label = "Select resolution type"
        
        self.fields['resolution_notes'].help_text = "This will be visible to both buyer and vendor"
        self.fields['admin_notes'].help_text = "Internal notes for admin reference only"
        self.fields['refund_amount'].help_text = "Required for refund resolutions"
    
    def clean(self):
        cleaned_data = super().clean()
        resolution_type = cleaned_data.get('resolution_type')
        refund_amount = cleaned_data.get('refund_amount')
        
        if resolution_type in ['full_refund', 'partial_refund']:
            if not refund_amount or refund_amount <= 0:
                raise ValidationError("Refund amount is required for refund resolutions")
            
            if self.dispute and refund_amount > self.dispute.order.total_amount:
                raise ValidationError("Refund amount cannot exceed order total")
        
        return cleaned_data
