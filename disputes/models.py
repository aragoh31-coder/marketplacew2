from django.db import models
from django.contrib.auth import get_user_model
from core.base_models import PrivacyModel
from orders.models import Order
import uuid

User = get_user_model()


class Dispute(PrivacyModel):
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('INVESTIGATING', 'Under Investigation'),
        ('RESOLVED', 'Resolved'),
        ('CLOSED', 'Closed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='dispute')
    complainant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='filed_disputes')
    respondent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_disputes')
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    resolution = models.TextField(blank=True)
    moderator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='moderated_disputes')
    
    def __str__(self):
        return f"Dispute {self.id} - Order {self.order.id}"


class DisputeEvidence(PrivacyModel):
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='evidence')
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE)
    description = models.TextField()
    steganographic_data = models.TextField(blank=True, null=True)  # Encrypted field
    file_attachment = models.FileField(upload_to='dispute_evidence/', blank=True, null=True)
    
    def __str__(self):
        return f"Evidence for Dispute {self.dispute.id}"
