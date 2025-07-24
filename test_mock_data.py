#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')
django.setup()

from django.contrib.auth import get_user_model
from products.models import Product, Category
from vendors.models import Vendor
from orders.models import Order
from wallets.models import Wallet
from messaging.models import Message

User = get_user_model()

print("🧪 Testing Mock Data...\n")

print("📂 Categories:")
categories = Category.objects.all()
for category in categories:
    product_count = category.products.count()
    print(f"  • {category.name}: {product_count} products")

print("\n👥 Premium Vendors:")
premium_vendors = ['CardMaster', 'DigitalDeals', 'CryptoCards', 'InstantGifts']
for username in premium_vendors:
    vendor_user = User.objects.filter(username=username).first()
    if vendor_user:
        vendor = vendor_user.vendor
        print(f"  • {vendor_user.username}: {vendor.products.count()} products, {vendor.trust_level} trust")
        print(f"    Rating: {vendor.rating}/5.00, Sales: ${vendor.total_sales}")

print("\n📦 Sample Products:")
products = Product.objects.filter(is_available=True)[:8]
for product in products:
    print(f"  • {product.name}: ₿{product.price_btc} / ɱ{product.price_xmr}")
    print(f"    Stock: {product.stock_quantity}, Vendor: {product.vendor.vendor_name}")

print("\n🛒 Test Buyers:")
test_buyers = ['CryptoShopper', 'GiftHunter', 'DigitalBuyer']
for username in test_buyers:
    buyer = User.objects.filter(username=username).first()
    if buyer:
        orders = buyer.orders.count()
        btc_wallet = buyer.wallets.filter(currency='BTC').first()
        xmr_wallet = buyer.wallets.filter(currency='XMR').first()
        print(f"  • {buyer.username}: {orders} orders")
        if btc_wallet and xmr_wallet:
            print(f"    Wallets: ₿{btc_wallet.balance} BTC, ɱ{xmr_wallet.balance} XMR")

print("\n📋 Order Statistics:")
total_orders = Order.objects.count()
order_statuses = Order.objects.values_list('status', flat=True)
status_counts = {}
for status in order_statuses:
    status_counts[status] = status_counts.get(status, 0) + 1

print(f"  Total Orders: {total_orders}")
for status, count in status_counts.items():
    print(f"  • {status}: {count}")

print("\n💬 Message Statistics:")
total_messages = Message.objects.count()
unread_messages = Message.objects.filter(is_read=False).count()
print(f"  Total Messages: {total_messages}")
print(f"  Unread Messages: {unread_messages}")

print("\n✅ Mock data validation complete!")
print("\n🔑 Login Credentials:")
print("  Vendors: CardMaster, DigitalDeals, CryptoCards (password: vendor123)")
print("  Buyers: CryptoShopper, GiftHunter, DigitalBuyer (password: buyer123)")
