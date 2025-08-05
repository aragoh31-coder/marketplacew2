import random
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from vendors.models import Vendor
from products.models import Product, Category
from wallets.models import Wallet, Transaction

User = get_user_model()


class Command(BaseCommand):
    help = 'Create mock data for testing the marketplace'

    def add_arguments(self, parser):
        parser.add_argument(
            '--vendors',
            type=int,
            default=5,
            help='Number of vendors to create'
        )
        parser.add_argument(
            '--products',
            type=int,
            default=20,
            help='Number of products to create'
        )

    def handle(self, *args, **options):
        self.stdout.write('Creating mock data...')
        
        categories = [
            'Digital Goods',
            'Gift Cards',
            'Software',
            'Services',
            'Electronics'
        ]
        
        for cat_name in categories:
            Category.objects.get_or_create(
                name=cat_name,
                defaults={'description': f'Category for {cat_name}'}
            )
        
        for i in range(options['vendors']):
            username = f'vendor_{i+1}'
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': f'{username}@example.com',
                    'is_active': True
                }
            )
            
            if created:
                user.set_password('testpass123')
                user.save()
            
            vendor, created = Vendor.objects.get_or_create(
                user=user,
                defaults={
                    'vendor_name': f'Vendor {i+1}',
                    'description': f'Test vendor {i+1} description',
                    'is_approved': True,
                    'trust_level': random.randint(1, 10)
                }
            )
            
            Wallet.objects.get_or_create(
                user=user,
                currency='BTC',
                defaults={'balance': Decimal('0.00000000')}
            )
            Wallet.objects.get_or_create(
                user=user,
                currency='XMR',
                defaults={'balance': Decimal('0.00000000')}
            )
        
        vendors = Vendor.objects.filter(is_approved=True)
        categories_qs = Category.objects.all()
        
        product_names = [
            'Premium Gift Card',
            'Digital Software License',
            'VPN Service',
            'Gaming Account',
            'Streaming Service',
            'Cloud Storage',
            'Digital Art',
            'E-book Collection',
            'Music Library',
            'Video Course'
        ]
        
        for i in range(options['products']):
            vendor = random.choice(vendors)
            category = random.choice(categories_qs)
            name = f"{random.choice(product_names)} {i+1}"
            
            Product.objects.get_or_create(
                name=name,
                vendor=vendor,
                category=category,
                defaults={
                    'description': f'High quality {name.lower()} with excellent features.',
                    'price_btc': Decimal(str(random.uniform(0.001, 0.1))),
                    'price_xmr': Decimal(str(random.uniform(0.01, 1.0))),
                    'stock_quantity': random.randint(1, 100),
                    'is_available': True,
                    'product_type': random.choice(['DIGITAL', 'GIFT_CARD', 'PHYSICAL'])
                }
            )
        
        for i in range(10):
            username = f'buyer_{i+1}'
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': f'{username}@example.com',
                    'is_active': True
                }
            )
            
            if created:
                user.set_password('testpass123')
                user.save()
            
            Wallet.objects.get_or_create(
                user=user,
                currency='BTC',
                defaults={'balance': Decimal(str(random.uniform(0.001, 0.01)))}
            )
            Wallet.objects.get_or_create(
                user=user,
                currency='XMR',
                defaults={'balance': Decimal(str(random.uniform(0.1, 1.0)))}
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {options["vendors"]} vendors and {options["products"]} products'
            )
        )
