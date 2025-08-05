#!/usr/bin/env python3
import secrets
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.models import Cart
from vendors.models import Vendor
from wallets.models import Wallet

User = get_user_model()


class Command(BaseCommand):
    help = "Creates specific test accounts for marketplace testing"

    def handle(self, *args, **options):
        self.stdout.write("🚀 Creating test accounts...")

        self.clear_test_accounts()

        buyers = self.create_buyer_accounts()
        vendors = self.create_vendor_accounts()
        admins = self.create_admin_accounts()

        self.stdout.write(self.style.SUCCESS("✅ Test accounts created successfully!"))
        self.print_account_summary(buyers, vendors, admins)

    def clear_test_accounts(self):
        """Clear existing test accounts"""
        self.stdout.write("🗑️  Clearing existing test accounts...")

        test_usernames = [
            "testbuyer1",
            "testbuyer2",
            "testbuyer3",
            "testvendor1",
            "testvendor2",
            "testvendor3",
            "testadmin1",
            "testadmin2",
        ]

        User.objects.filter(username__in=test_usernames).delete()
        self.stdout.write("✅ Test accounts cleared")

    def create_buyer_accounts(self):
        """Create 3 buyer test accounts"""
        self.stdout.write("🛒 Creating 3 buyer accounts...")

        buyers = []
        buyer_data = [
            {
                "username": "testbuyer1",
                "email": "testbuyer1@market.onion",
                "first_name": "Alice",
                "last_name": "Buyer",
                "total_trades": 15,
                "positive_feedback_count": 14,
                "feedback_score": 4.8,
            },
            {
                "username": "testbuyer2",
                "email": "testbuyer2@market.onion",
                "first_name": "Bob",
                "last_name": "Customer",
                "total_trades": 8,
                "positive_feedback_count": 8,
                "feedback_score": 5.0,
            },
            {
                "username": "testbuyer3",
                "email": "testbuyer3@market.onion",
                "first_name": "Charlie",
                "last_name": "Shopper",
                "total_trades": 3,
                "positive_feedback_count": 3,
                "feedback_score": 4.7,
            },
        ]

        for data in buyer_data:
            user = User.objects.create_user(
                username=data["username"],
                email=data["email"],
                password="testpass123",
                first_name=data["first_name"],
                last_name=data["last_name"],
                total_trades=data["total_trades"],
                positive_feedback_count=data["positive_feedback_count"],
                feedback_score=data["feedback_score"],
                is_vendor=False,
                default_currency="BTC",
            )

            Wallet.objects.create(
                user=user,
                balance_btc=Decimal("0.05000000"),
                balance_xmr=Decimal("25.000000000000"),
                escrow_btc=Decimal("0.00000000"),
                escrow_xmr=Decimal("0.000000000000"),
                daily_withdrawal_limit_btc=Decimal("1.00000000"),
                daily_withdrawal_limit_xmr=Decimal("100.000000000000"),
            )

            Cart.objects.create(user=user)

            buyers.append(user)
            self.stdout.write(f"  ✅ Created buyer: {user.username}")

        return buyers

    def create_vendor_accounts(self):
        """Create 3 vendor test accounts"""
        self.stdout.write("👥 Creating 3 vendor accounts...")

        vendors = []
        vendor_data = [
            {
                "username": "testvendor1",
                "email": "testvendor1@market.onion",
                "first_name": "David",
                "last_name": "Vendor",
                "vendor_name": "Premium Cards Pro",
                "description": "Trusted vendor specializing in premium gift cards. Fast delivery and excellent customer service.",
                "trust_level": "VERIFIED",
                "total_sales": Decimal("12500.00"),
                "rating": Decimal("4.92"),
                "total_trades": 85,
                "positive_feedback_count": 82,
            },
            {
                "username": "testvendor2",
                "email": "testvendor2@market.onion",
                "first_name": "Emma",
                "last_name": "Seller",
                "vendor_name": "Digital Goods Express",
                "description": "Instant delivery digital products. Gaming cards, streaming services, and more.",
                "trust_level": "TRUSTED",
                "total_sales": Decimal("8750.50"),
                "rating": Decimal("4.85"),
                "total_trades": 62,
                "positive_feedback_count": 59,
            },
            {
                "username": "testvendor3",
                "email": "testvendor3@market.onion",
                "first_name": "Frank",
                "last_name": "Merchant",
                "vendor_name": "Crypto Cards Hub",
                "description": "New vendor with competitive prices. Building reputation with quality service.",
                "trust_level": "NEW",
                "total_sales": Decimal("2100.25"),
                "rating": Decimal("4.75"),
                "total_trades": 18,
                "positive_feedback_count": 17,
            },
        ]

        for data in vendor_data:
            user = User.objects.create_user(
                username=data["username"],
                email=data["email"],
                password="testpass123",
                first_name=data["first_name"],
                last_name=data["last_name"],
                total_trades=data["total_trades"],
                positive_feedback_count=data["positive_feedback_count"],
                feedback_score=float(data["rating"]),
                is_vendor=True,
                default_currency="BTC",
                pgp_public_key=self.generate_mock_pgp_key(data["username"]),
                pgp_fingerprint=secrets.token_hex(20),
                pgp_login_enabled=True,
            )

            vendor = Vendor.objects.create(
                user=user,
                vendor_name=data["vendor_name"],
                description=data["description"],
                trust_level=data["trust_level"],
                total_sales=data["total_sales"],
                rating=data["rating"],
                is_approved=True,
            )

            Wallet.objects.create(
                user=user,
                balance_btc=Decimal("0.25000000"),
                balance_xmr=Decimal("150.000000000000"),
                escrow_btc=Decimal("0.01000000"),
                escrow_xmr=Decimal("5.000000000000"),
                daily_withdrawal_limit_btc=Decimal("2.00000000"),
                daily_withdrawal_limit_xmr=Decimal("200.000000000000"),
            )

            vendors.append(user)
            self.stdout.write(
                f"  ✅ Created vendor: {user.username} ({data['vendor_name']})"
            )

        return vendors

    def create_admin_accounts(self):
        """Create 2 admin test accounts"""
        self.stdout.write("👑 Creating 2 admin accounts...")

        admins = []
        admin_data = [
            {
                "username": "testadmin1",
                "email": "testadmin1@market.onion",
                "first_name": "Grace",
                "last_name": "Admin",
                "is_superuser": True,
                "is_staff": True,
            },
            {
                "username": "testadmin2",
                "email": "testadmin2@market.onion",
                "first_name": "Henry",
                "last_name": "Moderator",
                "is_superuser": True,
                "is_staff": True,
            },
        ]

        for data in admin_data:
            user = User.objects.create_user(
                username=data["username"],
                email=data["email"],
                password="testpass123",
                first_name=data["first_name"],
                last_name=data["last_name"],
                is_superuser=data["is_superuser"],
                is_staff=data["is_staff"],
                total_trades=0,
                positive_feedback_count=0,
                feedback_score=5.0,
                default_currency="BTC",
                pgp_public_key=self.generate_mock_pgp_key(data["username"]),
                pgp_fingerprint=secrets.token_hex(20),
                pgp_login_enabled=True,
            )

            Wallet.objects.create(
                user=user,
                balance_btc=Decimal("1.00000000"),
                balance_xmr=Decimal("500.000000000000"),
                escrow_btc=Decimal("0.00000000"),
                escrow_xmr=Decimal("0.000000000000"),
                daily_withdrawal_limit_btc=Decimal("10.00000000"),
                daily_withdrawal_limit_xmr=Decimal("1000.000000000000"),
            )

            admins.append(user)
            self.stdout.write(f"  ✅ Created admin: {user.username}")

        return admins

    def generate_mock_pgp_key(self, username):
        """Generate a mock PGP public key block"""
        return f"""-----BEGIN PGP PUBLIC KEY BLOCK-----

mQENBGTest{username}BCADUCjh8J7YPQockStart{username}MockKeyDataForTesting
ThisIsNotARealPGPKeyButLooksLikeOne1234567890ABCDEFGHIJKLMNOP
QRSTUVWXYZabcdefghijklmnopqrstuvwxyz1234567890+/=MoreMockData
{secrets.token_urlsafe(200)}
SomeMockPGPKeyDataContinuesHereForTestingPurposesOnly1234567890
={secrets.token_urlsafe(44)}
-----END PGP PUBLIC KEY BLOCK-----"""

    def print_account_summary(self, buyers, vendors, admins):
        """Print summary of created test accounts"""
        self.stdout.write("\n📊 Test Account Summary:")
        self.stdout.write("=" * 60)

        self.stdout.write(f"\n🛒 BUYER ACCOUNTS ({len(buyers)}):")
        for buyer in buyers:
            self.stdout.write(f"  Username: {buyer.username}")
            self.stdout.write(f"  Password: testpass123")
            self.stdout.write(f"  Email: {buyer.email}")
            self.stdout.write(f"  Trust Level: {buyer.get_trust_level()}")
            self.stdout.write(f"  Trades: {buyer.total_trades}")
            self.stdout.write("")

        self.stdout.write(f"👥 VENDOR ACCOUNTS ({len(vendors)}):")
        for vendor in vendors:
            vendor_profile = Vendor.objects.get(user=vendor)
            self.stdout.write(f"  Username: {vendor.username}")
            self.stdout.write(f"  Password: testpass123")
            self.stdout.write(f"  Email: {vendor.email}")
            self.stdout.write(f"  Vendor Name: {vendor_profile.vendor_name}")
            self.stdout.write(f"  Trust Level: {vendor_profile.trust_level}")
            self.stdout.write(f"  Rating: {vendor_profile.rating}")
            self.stdout.write("")

        self.stdout.write(f"👑 ADMIN ACCOUNTS ({len(admins)}):")
        for admin in admins:
            self.stdout.write(f"  Username: {admin.username}")
            self.stdout.write(f"  Password: testpass123")
            self.stdout.write(f"  Email: {admin.email}")
            self.stdout.write(f"  Superuser: {admin.is_superuser}")
            self.stdout.write(f"  Staff: {admin.is_staff}")
            self.stdout.write("")

        self.stdout.write("🔐 All accounts have PGP keys enabled for testing")
        self.stdout.write("💰 All accounts have pre-funded wallets")
        self.stdout.write(
            "🌐 Access via: http://eo256pnscr5zd4bw2p4c24nrh2vntjhlcqxy5iluselu4mq7wgzt7sqd.onion"
        )
