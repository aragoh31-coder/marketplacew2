from django.core.management.base import BaseCommand
from django.utils import timezone
from vendors.models import Vendor
from vendors.trust_calculator import VendorTrustCalculator

class Command(BaseCommand):
    help = 'Update trust levels for all vendors'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes'
        )
        parser.add_argument(
            '--vendor-id',
            type=str,
            help='Update trust level for specific vendor ID'
        )
        parser.add_argument(
            '--stale-only',
            action='store_true',
            help='Only update vendors with stale trust scores'
        )
    
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        vendor_id = options['vendor_id']
        stale_only = options['stale_only']
        
        if vendor_id:
            self.update_single_vendor(vendor_id, dry_run)
        elif stale_only:
            self.update_stale_vendors(dry_run)
        else:
            self.update_all_vendors(dry_run)
    
    def update_single_vendor(self, vendor_id, dry_run):
        """Update trust level for a single vendor"""
        try:
            vendor = Vendor.objects.get(id=vendor_id)
            
            if dry_run:
                trust_data = VendorTrustCalculator.calculate_trust_score(vendor)
                self.stdout.write(
                    f"[DRY RUN] Vendor {vendor.user.username}: "
                    f"Current: {vendor.trust_score} ({vendor.trust_level}) -> "
                    f"New: {trust_data['trust_score']} ({trust_data['trust_level']})"
                )
            else:
                trust_data = VendorTrustCalculator.update_vendor_trust(vendor)
                if trust_data:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Updated vendor {vendor.user.username}: "
                            f"{trust_data['trust_score']} ({trust_data['trust_level']})"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.ERROR(f"Failed to update vendor {vendor.user.username}")
                    )
                    
        except Vendor.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Vendor with ID {vendor_id} not found"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error updating vendor {vendor_id}: {e}"))
    
    def update_stale_vendors(self, dry_run):
        """Update vendors with stale trust scores"""
        from datetime import timedelta
        from django.db.models import Q
        
        cutoff_time = timezone.now() - timedelta(days=7)
        
        stale_vendors = Vendor.objects.filter(
            Q(trust_updated_at__lt=cutoff_time) | Q(trust_updated_at__isnull=True),
            is_active=True
        )
        
        self.stdout.write(f"Found {stale_vendors.count()} vendors with stale trust scores")
        
        updated_count = 0
        
        for vendor in stale_vendors:
            try:
                if dry_run:
                    trust_data = VendorTrustCalculator.calculate_trust_score(vendor)
                    self.stdout.write(
                        f"[DRY RUN] Vendor {vendor.user.username}: "
                        f"Current: {vendor.trust_score} ({vendor.trust_level}) -> "
                        f"New: {trust_data['trust_score']} ({trust_data['trust_level']})"
                    )
                else:
                    trust_data = VendorTrustCalculator.update_vendor_trust(vendor)
                    if trust_data:
                        updated_count += 1
                        self.stdout.write(f"Updated {vendor.user.username}")
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error updating vendor {vendor.user.username}: {e}")
                )
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Updated {updated_count}/{stale_vendors.count()} stale vendors")
            )
    
    def update_all_vendors(self, dry_run):
        """Update trust levels for all active vendors"""
        vendors = Vendor.objects.filter(is_active=True)
        
        self.stdout.write(f"Found {vendors.count()} active vendors")
        
        updated_count = 0
        
        for vendor in vendors:
            try:
                if dry_run:
                    trust_data = VendorTrustCalculator.calculate_trust_score(vendor)
                    self.stdout.write(
                        f"[DRY RUN] Vendor {vendor.user.username}: "
                        f"Current: {vendor.trust_score} ({vendor.trust_level}) -> "
                        f"New: {trust_data['trust_score']} ({trust_data['trust_level']})"
                    )
                else:
                    trust_data = VendorTrustCalculator.update_vendor_trust(vendor)
                    if trust_data:
                        updated_count += 1
                        if updated_count % 10 == 0:
                            self.stdout.write(f"Updated {updated_count} vendors...")
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error updating vendor {vendor.user.username}: {e}")
                )
        
        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Updated {updated_count}/{vendors.count()} vendors")
            )
        else:
            self.stdout.write(f"[DRY RUN] Would update {vendors.count()} vendors")
