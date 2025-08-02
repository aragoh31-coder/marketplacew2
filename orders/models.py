from django.db import models
from django.contrib.auth import get_user_model
from core.base_models import PrivacyModel
from products.models import Product
from vendors.models import Vendor
import uuid

User = get_user_model()


class Order(PrivacyModel):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Payment'),
        ('PAID', 'Paid'),
        ('PROCESSING', 'Processing'),
        ('SHIPPED', 'Shipped'),
        ('DELIVERED', 'Delivered'),
        ('CANCELLED', 'Cancelled'),
        ('DISPUTED', 'Disputed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    buyer_wallet = models.ForeignKey('wallets.Wallet', on_delete=models.CASCADE, related_name='buyer_orders', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    total_btc = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    total_xmr = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    escrow_address = models.CharField(max_length=255, blank=True, null=True)
    shipping_address = models.TextField(blank=True)  # Encrypted field
    
    def __str__(self):
        return f"Order {self.id} - {self.user.username}"


class OrderItem(PrivacyModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    price_btc = models.DecimalField(max_digits=20, decimal_places=8)
    price_xmr = models.DecimalField(max_digits=20, decimal_places=8)
    
    def __str__(self):
        return f"{self.quantity}x {self.product.name}"


class Cart(PrivacyModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart')
    
    def __str__(self):
        return f"Cart for {self.user.username}"


class CartItem(PrivacyModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)
    
    class Meta:
        unique_together = ['cart', 'product']
    
    def __str__(self):
        return f"{self.quantity}x {self.product.name} in cart"
