from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from core.base_models import PrivacyModel
import hashlib
import uuid

User = get_user_model()


class ProductReview(PrivacyModel):
    """Product review system with verification and cryptographic proofs"""
    
    RATING_CHOICES = [(i, i) for i in range(1, 6)]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='reviews')
    order_item = models.OneToOneField('orders.OrderItem', on_delete=models.CASCADE, related_name='review')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_reviews')
    
    rating = models.IntegerField(choices=RATING_CHOICES, validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=100)
    comment = models.TextField(max_length=2000)
    
    # Verification fields
    verified_purchase = models.BooleanField(default=False)
    purchase_proof = models.CharField(max_length=64)  # Hash of order ID + user ID
    
    # Cryptographic proof of review authenticity
    review_hash = models.CharField(max_length=64, unique=True)
    previous_hash = models.CharField(max_length=64, blank=True)  # For blockchain-like verification
    
    # Helpfulness voting
    helpful_votes = models.IntegerField(default=0)
    unhelpful_votes = models.IntegerField(default=0)
    helpfulness_score = models.FloatField(default=0)
    
    # Vendor response
    vendor_response = models.TextField(blank=True, max_length=1000)
    vendor_responded_at = models.DateTimeField(null=True, blank=True)
    
    # Incentive tracking
    incentive_granted = models.BooleanField(default=False)
    incentive_type = models.CharField(max_length=50, blank=True)  # 'discount', 'points', etc.
    incentive_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Time decay for reputation
    decay_factor = models.FloatField(default=1.0)
    last_decay_update = models.DateTimeField(default=timezone.now)
    
    # Moderation
    flagged = models.BooleanField(default=False)
    moderated = models.BooleanField(default=False)
    hidden = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'verified_purchase', '-created_at']),
            models.Index(fields=['reviewer', '-created_at']),
            models.Index(fields=['helpfulness_score', '-created_at']),
        ]
        unique_together = ['order_item', 'reviewer']  # One review per purchase
    
    def generate_review_hash(self):
        """Generate cryptographic hash for review integrity"""
        data = f"{self.product.id}{self.reviewer.id}{self.rating}{self.comment}{self.created_at}"
        self.review_hash = hashlib.sha256(data.encode()).hexdigest()
        
        # Chain to previous review for blockchain-like verification
        last_review = ProductReview.objects.filter(
            product=self.product,
            created_at__lt=self.created_at
        ).order_by('-created_at').first()
        
        if last_review:
            self.previous_hash = last_review.review_hash
    
    def verify_purchase(self):
        """Verify this is a legitimate purchase"""
        # Check if order item exists and is completed
        if not self.order_item:
            return False
        
        if self.order_item.order.status not in ['DELIVERED', 'COMPLETED']:
            return False
        
        # Generate purchase proof
        proof_data = f"{self.order_item.order.id}{self.reviewer.id}"
        self.purchase_proof = hashlib.sha256(proof_data.encode()).hexdigest()
        self.verified_purchase = True
        
        return True
    
    def calculate_helpfulness(self):
        """Calculate helpfulness score"""
        total_votes = self.helpful_votes + self.unhelpful_votes
        if total_votes == 0:
            self.helpfulness_score = 0
        else:
            # Wilson score for better ranking
            positive_ratio = self.helpful_votes / total_votes
            z = 1.96  # 95% confidence
            
            self.helpfulness_score = (
                positive_ratio + z*z/(2*total_votes) - 
                z * ((positive_ratio * (1-positive_ratio) + z*z/(4*total_votes)) / total_votes) ** 0.5
            ) / (1 + z*z/total_votes)
    
    def apply_time_decay(self):
        """Apply time decay to review weight for reputation calculation"""
        days_old = (timezone.now() - self.created_at).days
        
        if days_old > 30:
            # Start decay after 30 days
            decay_rate = 0.95  # 5% decay per month
            months_old = days_old / 30
            self.decay_factor = decay_rate ** months_old
            self.last_decay_update = timezone.now()
    
    def grant_incentive(self, incentive_type='discount', value=5):
        """Grant incentive for detailed review"""
        if self.incentive_granted:
            return False
        
        # Check review quality
        if len(self.comment) < 100:  # Minimum 100 characters
            return False
        
        self.incentive_granted = True
        self.incentive_type = incentive_type
        self.incentive_value = value
        self.save()
        
        return True
    
    def save(self, *args, **kwargs):
        if not self.review_hash:
            self.generate_review_hash()
        if not self.verified_purchase:
            self.verify_purchase()
        super().save(*args, **kwargs)


class ReviewVote(PrivacyModel):
    """Track review helpfulness votes"""
    
    review = models.ForeignKey(ProductReview, on_delete=models.CASCADE, related_name='votes')
    voter = models.ForeignKey(User, on_delete=models.CASCADE)
    helpful = models.BooleanField()
    
    class Meta:
        unique_together = ['review', 'voter']
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update review helpfulness scores
        self.review.helpful_votes = self.review.votes.filter(helpful=True).count()
        self.review.unhelpful_votes = self.review.votes.filter(helpful=False).count()
        self.review.calculate_helpfulness()
        self.review.save()


class BuyerReputation(PrivacyModel):
    """Buyer reputation scoring system"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='buyer_reputation')
    
    # Order statistics
    completed_orders = models.IntegerField(default=0)
    cancelled_orders = models.IntegerField(default=0)
    disputed_orders = models.IntegerField(default=0)
    
    # Financial statistics
    total_spent_btc = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    total_spent_xmr = models.DecimalField(max_digits=20, decimal_places=12, default=0)
    
    # Review statistics
    reviews_written = models.IntegerField(default=0)
    helpful_reviews = models.IntegerField(default=0)
    
    # Behavior scores
    dispute_rate = models.FloatField(default=0)
    completion_rate = models.FloatField(default=0)
    response_time_hours = models.FloatField(default=0)
    
    # Reputation score (0-100)
    reputation_score = models.FloatField(default=50)
    trust_level = models.CharField(max_length=20, default='NEW')
    
    # Flags
    is_trusted = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_banned = models.BooleanField(default=False)
    
    last_calculated = models.DateTimeField(default=timezone.now)
    
    class Meta:
        indexes = [
            models.Index(fields=['reputation_score', 'trust_level']),
        ]
    
    def calculate_reputation(self):
        """Calculate buyer reputation score"""
        score = 50  # Base score
        
        # Completion rate impact (max +30)
        if self.completed_orders > 0:
            self.completion_rate = self.completed_orders / (self.completed_orders + self.cancelled_orders)
            score += self.completion_rate * 30
        
        # Dispute rate impact (max -20)
        if self.completed_orders > 0:
            self.dispute_rate = self.disputed_orders / self.completed_orders
            score -= self.dispute_rate * 20
        
        # Review quality impact (max +10)
        if self.reviews_written > 0:
            review_quality = self.helpful_reviews / self.reviews_written
            score += review_quality * 10
        
        # Order volume impact (max +10)
        if self.completed_orders >= 50:
            score += 10
        elif self.completed_orders >= 20:
            score += 5
        elif self.completed_orders >= 10:
            score += 2
        
        # Cap at 0-100
        self.reputation_score = max(0, min(100, score))
        
        # Set trust level
        if self.reputation_score >= 90 and self.completed_orders >= 50:
            self.trust_level = 'ELITE'
            self.is_trusted = True
        elif self.reputation_score >= 75 and self.completed_orders >= 20:
            self.trust_level = 'TRUSTED'
            self.is_trusted = True
        elif self.reputation_score >= 60 and self.completed_orders >= 10:
            self.trust_level = 'ESTABLISHED'
        elif self.completed_orders >= 5:
            self.trust_level = 'REGULAR'
        else:
            self.trust_level = 'NEW'
        
        self.last_calculated = timezone.now()
        self.save()


class VendorResponse(PrivacyModel):
    """Vendor responses to reviews"""
    
    review = models.OneToOneField(ProductReview, on_delete=models.CASCADE, related_name='vendor_reply')
    vendor = models.ForeignKey('vendors.Vendor', on_delete=models.CASCADE)
    response = models.TextField(max_length=1000)
    
    class Meta:
        ordering = ['-created_at']