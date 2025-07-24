from django.db import models
from django.contrib.auth import get_user_model
from core.base_models import PrivacyModel
import uuid

User = get_user_model()


class SupportTicket(PrivacyModel):
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('IN_PROGRESS', 'In Progress'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')
    subject = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='MEDIUM')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    
    def __str__(self):
        return f"Ticket {self.id} - {self.subject}"


class Feedback(PrivacyModel):
    FEEDBACK_TYPES = [
        ('BUG', 'Bug Report'),
        ('FEATURE', 'Feature Request'),
        ('GENERAL', 'General Feedback'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedback')
    feedback_type = models.CharField(max_length=20, choices=FEEDBACK_TYPES)
    content = models.TextField()
    ring_signature = models.TextField(blank=True, null=True)  # Placeholder for ring signature
    
    def __str__(self):
        return f"{self.feedback_type} feedback from {self.user.username}"
