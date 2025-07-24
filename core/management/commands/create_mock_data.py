from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import random
import secrets
from vendors.models import Vendor, VendorRating
from products.models import Product, Category
from wallets.models import Wallet, Transaction
from orders.models import Order, OrderItem, Cart
from messaging.models import Message, MessageThread

User = get_user_model()

class Command(BaseCommand):
    help = 'Creates mock vendor accounts and products for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--vendors',
            type=int,
            default=10,
            help='Number of vendors to create'
        )
        parser.add_argument(
            '--products',
            type=int,
            default=50,
            help='Number of products to create'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing mock data first'
        )

    def handle(self, *args, **options):
        self.stdout.write("🚀 Creating mock marketplace data...")
        
        if options['clear']:
            self.clear_mock_data()
        
        categories = self.create_categories()
        vendors = self.create_vendors(options['vendors'])
        products = self.create_products(vendors, categories, options['products'])
        buyers = self.create_buyers()
        self.create_orders(buyers, products)
        self.create_messages(vendors, buyers)
        
        self.stdout.write(self.style.SUCCESS("✅ Mock data created successfully!"))
        self.print_summary()

    def clear_mock_data(self):
        """Clear existing mock data"""
        self.stdout.write("🗑️  Clearing existing mock data...")
        User.objects.filter(username__startswith='mock_').delete()
        User.objects.filter(username__in=[
            'CardMaster', 'DigitalDeals', 'CryptoCards', 'GiftHub', 'InstantGifts',
            'CryptoShopper', 'GiftHunter', 'DigitalBuyer', 'AnonCustomer', 'MarketUser', 'CardCollector'
        ]).delete()
        self.stdout.write("✅ Mock data cleared")

    def create_categories(self):
        """Create product categories"""
        self.stdout.write("📂 Creating categories...")
        
        category_data = [
            ('Amazon', 'Amazon gift cards and store credit'),
            ('Steam', 'Steam wallet codes and gaming cards'),
            ('Google Play', 'Google Play store credit and app purchases'),
            ('Apple', 'Apple Store and iTunes gift cards'),
            ('Gaming', 'PlayStation, Xbox, and other gaming platforms'),
            ('Streaming', 'Netflix, Spotify, and entertainment services'),
            ('Shopping', 'eBay, retail, and general shopping cards'),
            ('Transport', 'Uber, Lyft, and transportation services'),
        ]
        
        categories = []
        for name, description in category_data:
            category, created = Category.objects.get_or_create(
                name=name,
                defaults={'description': description}
            )
            categories.append(category)
            if created:
                self.stdout.write(f"  ✅ Created category: {name}")
        
        return categories

    def create_vendors(self, count):
        """Create mock vendor accounts"""
        self.stdout.write(f"👥 Creating {count} vendors...")
        
        vendor_data = [
            {
                'username': 'CardMaster',
                'vendor_name': 'CardMaster Premium',
                'description': 'Premium gift cards at competitive prices. 5+ years experience in digital goods.',
                'trust_level': 'PREMIUM',
                'total_sales': Decimal('15430.50'),
                'rating': Decimal('4.95'),
                'pgp_enabled': True,
            },
            {
                'username': 'DigitalDeals',
                'vendor_name': 'Digital Deals UK',
                'description': 'Instant delivery digital cards. Trusted vendor since 2019 with excellent support.',
                'trust_level': 'VERIFIED',
                'total_sales': Decimal('8920.25'),
                'rating': Decimal('4.88'),
                'pgp_enabled': True,
            },
            {
                'username': 'CryptoCards',
                'vendor_name': 'Crypto Cards Pro',
                'description': 'Specializing in gaming gift cards. Lightning fast delivery and competitive rates.',
                'trust_level': 'PREMIUM',
                'total_sales': Decimal('21030.75'),
                'rating': Decimal('4.92'),
                'pgp_enabled': True,
            },
            {
                'username': 'GiftHub',
                'vendor_name': 'Gift Hub Store',
                'description': 'Wide selection of retail gift cards. Best prices guaranteed with 24/7 support.',
                'trust_level': 'TRUSTED',
                'total_sales': Decimal('5670.00'),
                'rating': Decimal('4.85'),
                'pgp_enabled': False,
            },
            {
                'username': 'InstantGifts',
                'vendor_name': 'Instant Gifts Pro',
                'description': 'Premium vendor with instant automated delivery. Highest trust rating.',
                'trust_level': 'PREMIUM',
                'total_sales': Decimal('34210.90'),
                'rating': Decimal('4.97'),
                'pgp_enabled': True,
            },
        ]
        
        vendors = []
        
        for vdata in vendor_data[:min(count, len(vendor_data))]:
            user, created = User.objects.get_or_create(
                username=vdata['username'],
                defaults={
                    'email': f"{vdata['username'].lower()}@market.onion",
                    'is_vendor': True,
                    'total_trades': random.randint(100, 500),
                    'positive_feedback_count': random.randint(95, 500),
                    'feedback_score': float(vdata['rating']),
                }
            )
            
            if created:
                user.set_password('vendor123')
                if vdata['pgp_enabled']:
                    user.pgp_public_key = self.generate_mock_pgp_key(user.username)
                    user.pgp_fingerprint = secrets.token_hex(20)
                    user.pgp_login_enabled = random.choice([True, False])
                user.save()
            
            vendor, created = Vendor.objects.get_or_create(
                user=user,
                defaults={
                    'vendor_name': vdata['vendor_name'],
                    'description': vdata['description'],
                    'trust_level': vdata['trust_level'],
                    'total_sales': vdata['total_sales'],
                    'rating': vdata['rating'],
                    'is_approved': True,
                }
            )
            
            self.create_vendor_wallets(user)
            vendors.append(vendor)
            self.stdout.write(f"  ✅ Created vendor: {user.username}")
        
        for i in range(len(vendor_data), count):
            username = f"mock_vendor_{i+1}"
            user = User.objects.create_user(
                username=username,
                email=f"{username}@market.onion",
                password='vendor123',
                is_vendor=True,
                total_trades=random.randint(10, 100),
                positive_feedback_count=random.randint(8, 95),
                feedback_score=random.uniform(4.0, 4.9),
            )
            
            vendor = Vendor.objects.create(
                user=user,
                vendor_name=f"Vendor {i+1}",
                description=f"Trusted vendor specializing in digital goods. Fast delivery guaranteed.",
                trust_level=random.choice(['NEW', 'TRUSTED', 'VERIFIED']),
                total_sales=Decimal(str(random.uniform(100, 5000))),
                rating=Decimal(str(random.uniform(4.0, 4.9))),
                is_approved=random.choice([True, False]),
            )
            
            self.create_vendor_wallets(user)
            vendors.append(vendor)
        
        return vendors

    def create_vendor_wallets(self, user):
        """Create wallet for vendor"""
        Wallet.objects.get_or_create(
            user=user,
            defaults={
                'balance_btc': Decimal(str(random.uniform(0.1, 5.0))),
                'balance_xmr': Decimal(str(random.uniform(10, 500))),
                'escrow_btc': Decimal('0.00000000'),
                'escrow_xmr': Decimal('0.000000000000'),
                'daily_withdrawal_limit_btc': Decimal('1.00000000'),
                'daily_withdrawal_limit_xmr': Decimal('100.000000000000'),
            }
        )

    def create_products(self, vendors, categories, count):
        """Create mock products"""
        self.stdout.write(f"📦 Creating {count} products...")
        
        product_templates = [
            {
                'name_template': 'Amazon Gift Card ${value} USD',
                'category': 'Amazon',
                'description': 'Genuine Amazon gift card. Instant delivery after payment confirmation. Can be redeemed on Amazon.com for any purchase.',
                'product_type': 'GIFT_CARD',
                'price_range': (10, 500),
            },
            {
                'name_template': 'Steam Wallet Card ${value} USD',
                'category': 'Steam',
                'description': 'Steam wallet code for gaming purchases. Works worldwide. Instant digital delivery within minutes.',
                'product_type': 'DIGITAL',
                'price_range': (10, 100),
            },
            {
                'name_template': 'Google Play Gift Card ${value}',
                'category': 'Google Play',
                'description': 'Google Play store credit. Perfect for apps, games, movies, and subscriptions. Region: USA.',
                'product_type': 'GIFT_CARD',
                'price_range': (10, 100),
            },
            {
                'name_template': 'Apple Gift Card ${value}',
                'category': 'Apple',
                'description': 'Apple Store & iTunes gift card. Valid for all Apple services including App Store, iTunes, and Apple Music.',
                'product_type': 'GIFT_CARD',
                'price_range': (10, 200),
            },
            {
                'name_template': 'PlayStation Store Card ${value}',
                'category': 'Gaming',
                'description': 'PSN wallet top-up. Region: USA. Digital delivery within minutes. Perfect for games and DLC.',
                'product_type': 'DIGITAL',
                'price_range': (10, 100),
            },
            {
                'name_template': 'Xbox Gift Card ${value}',
                'category': 'Gaming',
                'description': 'Xbox Live credit. Works for games, subscriptions, and content. Instant delivery guaranteed.',
                'product_type': 'DIGITAL',
                'price_range': (10, 100),
            },
            {
                'name_template': 'Netflix Gift Card ${value}',
                'category': 'Streaming',
                'description': 'Netflix subscription credit. No expiration date. Works in all supported regions.',
                'product_type': 'GIFT_CARD',
                'price_range': (25, 100),
            },
            {
                'name_template': 'Spotify Premium ${value}',
                'category': 'Streaming',
                'description': 'Spotify Premium subscription code. Instant activation. Enjoy ad-free music streaming.',
                'product_type': 'DIGITAL',
                'price_range': (10, 60),
            },
        ]
        
        products = []
        card_values = [10, 25, 50, 100, 200, 500]
        
        for i in range(count):
            template = random.choice(product_templates)
            vendor = random.choice(vendors)
            
            value = random.choice(card_values)
            if value > template['price_range'][1]:
                value = template['price_range'][1]
            
            discount = random.uniform(0.85, 0.95)
            base_price = value * discount
            
            btc_rate = random.uniform(45000, 55000)
            xmr_rate = random.uniform(150, 200)
            
            price_btc = Decimal(str(base_price / btc_rate)).quantize(Decimal('0.00000001'))
            price_xmr = Decimal(str(base_price / xmr_rate)).quantize(Decimal('0.00000001'))
            
            name = template['name_template'].replace('${value}', str(value))
            
            category = next((c for c in categories if c.name == template['category']), categories[0])
            
            product = Product.objects.create(
                vendor=vendor,
                category=category,
                name=name,
                description=template['description'] + f"\n\nVendor: {vendor.vendor_name}\nTrust Level: {vendor.trust_level}",
                product_type=template['product_type'],
                price_btc=price_btc,
                price_xmr=price_xmr,
                stock_quantity=random.randint(5, 100),
                is_available=True,
            )
            
            products.append(product)
        
        self.stdout.write(f"  ✅ Created {len(products)} products")
        return products

    def create_buyers(self):
        """Create sample buyer accounts"""
        self.stdout.write("🛒 Creating buyer accounts...")
        
        buyers = []
        buyer_names = [
            'CryptoShopper', 'GiftHunter', 'DigitalBuyer',
            'AnonCustomer', 'MarketUser', 'CardCollector'
        ]
        
        for name in buyer_names:
            user, created = User.objects.get_or_create(
                username=name,
                defaults={
                    'email': f"{name.lower()}@customer.onion",
                    'total_trades': random.randint(5, 50),
                    'positive_feedback_count': random.randint(4, 48),
                    'feedback_score': random.uniform(4.5, 5.0),
                }
            )
            
            if created:
                user.set_password('buyer123')
                user.save()
                
                self.create_buyer_wallets(user)
                Cart.objects.get_or_create(user=user)
                
                self.stdout.write(f"  ✅ Created buyer: {user.username}")
            
            buyers.append(user)
        
        for i in range(len(buyer_names), 10):
            username = f"buyer_{i+1}"
            user = User.objects.create_user(
                username=username,
                email=f"{username}@customer.onion",
                password='buyer123',
                total_trades=random.randint(1, 20),
                positive_feedback_count=random.randint(1, 19),
                feedback_score=random.uniform(4.0, 5.0),
            )
            
            self.create_buyer_wallets(user)
            Cart.objects.create(user=user)
            buyers.append(user)
        
        return buyers

    def create_buyer_wallets(self, user):
        """Create wallet for buyer"""
        Wallet.objects.create(
            user=user,
            balance_btc=Decimal(str(random.uniform(0.01, 0.5))),
            balance_xmr=Decimal(str(random.uniform(1, 50))),
            escrow_btc=Decimal('0.00000000'),
            escrow_xmr=Decimal('0.000000000000'),
            daily_withdrawal_limit_btc=Decimal('1.00000000'),
            daily_withdrawal_limit_xmr=Decimal('100.000000000000'),
        )

    def create_orders(self, buyers, products):
        """Create sample orders"""
        self.stdout.write("📋 Creating sample orders...")
        
        order_count = 0
        
        for buyer in buyers[:6]:
            num_orders = random.randint(1, 5)
            
            for _ in range(num_orders):
                order_date = timezone.now() - timezone.timedelta(
                    days=random.randint(0, 30),
                    hours=random.randint(0, 23)
                )
                
                order = Order.objects.create(
                    user=buyer,
                    status=random.choice(['DELIVERED', 'SHIPPED', 'PAID', 'PENDING']),
                    total_btc=Decimal('0'),
                    total_xmr=Decimal('0'),
                    escrow_address=f"escrow_{secrets.token_hex(16)}",
                    shipping_address='Encrypted shipping address for privacy',
                    created_at=order_date,
                )
                
                num_items = random.randint(1, 3)
                order_total_btc = Decimal('0')
                order_total_xmr = Decimal('0')
                
                for _ in range(num_items):
                    product = random.choice(products)
                    quantity = random.randint(1, min(3, product.stock_quantity))
                    
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        quantity=quantity,
                        price_btc=product.price_btc,
                        price_xmr=product.price_xmr,
                    )
                    
                    order_total_btc += product.price_btc * quantity
                    order_total_xmr += product.price_xmr * quantity
                
                order.total_btc = order_total_btc
                order.total_xmr = order_total_xmr
                order.save()
                order_count += 1
        
        self.stdout.write(f"  ✅ Created {order_count} orders")

    def create_messages(self, vendors, buyers):
        """Create sample messages between users"""
        self.stdout.write("💬 Creating sample messages...")
        
        message_templates = [
            "Hi, is this card still available?",
            "When will you ship my order?",
            "Can you do a bulk discount for 10 cards?",
            "Thanks for the fast delivery!",
            "Do you have any $100 Steam cards in stock?",
            "Order received, great service as always!",
            "Can you confirm the card is unused?",
            "What regions does this card work in?",
            "Is instant delivery available for this item?",
            "Perfect transaction, will buy again!",
        ]
        
        message_count = 0
        
        for _ in range(25):
            sender = random.choice(buyers)
            vendor = random.choice(vendors)
            recipient = vendor.user
            
            if random.choice([True, False]):
                sender, recipient = recipient, sender
            
            Message.objects.create(
                sender=sender,
                recipient=recipient,
                subject=f"Re: {random.choice(['Order inquiry', 'Product question', 'Delivery status', 'Bulk order'])}",
                content=random.choice(message_templates),
                is_read=random.choice([True, False]),
                created_at=timezone.now() - timezone.timedelta(
                    days=random.randint(0, 7),
                    hours=random.randint(0, 23)
                ),
            )
            message_count += 1
        
        self.stdout.write(f"  ✅ Created {message_count} messages")

    def generate_mock_pgp_key(self, username):
        """Generate a mock PGP public key block"""
        return f"""-----BEGIN PGP PUBLIC KEY BLOCK-----

mQENBGMocksBCADUCjh8J7YPQockStart{username}MockKeyDataForTesting
ThisIsNotARealPGPKeyButLooksLikeOne1234567890ABCDEFGHIJKLMNOP
QRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890+/=MoreMockData
{secrets.token_urlsafe(200)}
SomeMockPGPKeyDataContinuesHereForTestingPurposesOnly1234567890
={secrets.token_urlsafe(44)}
-----END PGP PUBLIC KEY BLOCK-----"""

    def print_summary(self):
        """Print summary of created data"""
        self.stdout.write("\n📊 Mock Data Summary:")
        self.stdout.write("="*50)
        
        vendors = Vendor.objects.count()
        products = Product.objects.count()
        buyers = User.objects.filter(is_vendor=False).count()
        orders = Order.objects.count()
        messages = Message.objects.count()
        categories = Category.objects.count()
        
        self.stdout.write(f"📂 Categories: {categories}")
        self.stdout.write(f"👥 Vendors: {vendors}")
        self.stdout.write(f"📦 Products: {products}")
        self.stdout.write(f"🛒 Buyers: {buyers}")
        self.stdout.write(f"📋 Orders: {orders}")
        self.stdout.write(f"💬 Messages: {messages}")
        
        self.stdout.write("\n🔑 Test Accounts:")
        self.stdout.write("-"*50)
        self.stdout.write("Premium Vendors:")
        self.stdout.write("  • CardMaster (password: vendor123) - 95% trust, PGP enabled")
        self.stdout.write("  • DigitalDeals (password: vendor123) - UK based, verified")
        self.stdout.write("  • CryptoCards (password: vendor123) - Gaming specialist")
        self.stdout.write("  • InstantGifts (password: vendor123) - Highest rated")
        self.stdout.write("")
        self.stdout.write("Test Buyers:")
        self.stdout.write("  • CryptoShopper (password: buyer123) - Active buyer")
        self.stdout.write("  • GiftHunter (password: buyer123) - Has order history")
        self.stdout.write("  • DigitalBuyer (password: buyer123) - Regular customer")
        self.stdout.write("")
        self.stdout.write("Product Categories:")
        self.stdout.write("  • Amazon, Steam, Google Play, Apple gift cards")
        self.stdout.write("  • Gaming (PlayStation, Xbox), Streaming (Netflix, Spotify)")
        self.stdout.write("  • Price range: $10-$500 with 5-15% discounts")
        self.stdout.write("-"*50)
        self.stdout.write("\n🚀 Ready for testing! Login with any account above.")
