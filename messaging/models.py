from django.db import models
from django.contrib.auth import get_user_model
from core.base_models import PrivacyModel
import uuid

User = get_user_model()


class Message(PrivacyModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    subject = models.CharField(max_length=255)
    content = models.TextField()  # PGP encrypted content
    is_read = models.BooleanField(default=False)
    pgp_signature = models.TextField(blank=True, null=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.subject}"


class MessageThread(PrivacyModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participants = models.ManyToManyField(User, related_name='message_threads')
    subject = models.CharField(max_length=255)
    last_message = models.ForeignKey(Message, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"Thread: {self.subject}"
