from celery import shared_task
from django.utils import timezone
from django.core.cache import cache
import logging
import subprocess

from .models import Vendor
from products.models import Product

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def create_low_stock_notification(self, vendor_id, product_ids):
    """Create in-app notification for low stock instead of email."""
    try:
        from .models import VendorNotification
        vendor = Vendor.objects.get(id=vendor_id)
        products = Product.objects.filter(id__in=product_ids)
        
        product_names = [p.name for p in products]
        if len(product_names) > 3:
            message = f"Products running low on stock: {', '.join(product_names[:3])} and {len(product_names) - 3} more."
        else:
            message = f"Products running low on stock: {', '.join(product_names)}"
        
        VendorNotification.objects.create(
            vendor=vendor,
            title=f'Low Stock Alert - {len(products)} Products Need Attention',
            message=message,
            notification_type='low_stock'
        )
        
        logger.info(f"Low stock notification created for vendor {vendor_id}")
        return f"Notification created for vendor {vendor_id} for {len(products)} products"
        
    except Vendor.DoesNotExist:
        logger.error(f"Vendor {vendor_id} not found")
        return "Vendor not found"
    except Exception as e:
        logger.error(f"Failed to create low stock notification: {str(e)}")
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))

@shared_task
def create_new_order_notification(vendor_id, order_id):
    """Create notification for new orders."""
    try:
        from .models import VendorNotification
        vendor = Vendor.objects.get(id=vendor_id)
        
        VendorNotification.objects.create(
            vendor=vendor,
            title='New Order Received',
            message=f'You have received a new order #{order_id}. Please check your orders dashboard.',
            notification_type='new_order'
        )
        
        logger.info(f"New order notification created for vendor {vendor_id}")
        
    except Vendor.DoesNotExist:
        logger.error(f"Vendor {vendor_id} not found for order notification")
    except Exception as e:
        logger.error(f"Failed to create order notification: {str(e)}")

@shared_task
def create_feedback_notification(vendor_id, feedback_id):
    """Create notification for new feedback."""
    try:
        from .models import VendorNotification
        vendor = Vendor.objects.get(id=vendor_id)
        
        VendorNotification.objects.create(
            vendor=vendor,
            title='New Customer Feedback',
            message=f'You have received new customer feedback. Please check your feedback dashboard to respond.',
            notification_type='new_feedback'
        )
        
        logger.info(f"Feedback notification created for vendor {vendor_id}")
        
    except Vendor.DoesNotExist:
        logger.error(f"Vendor {vendor_id} not found for feedback notification")
    except Exception as e:
        logger.error(f"Failed to create feedback notification: {str(e)}")

@shared_task
def update_vendor_metrics():
    """Periodic task to update vendor metrics cache."""
    vendors = Vendor.objects.filter(is_approved=True)
    
    for vendor in vendors:
        try:
            metrics = {
                'average_rating': vendor.rating,
                'total_sales': vendor.total_sales,
                'active_products': vendor.products.filter(is_available=True).count(),
            }
            
            cache_key = f'vendor_metrics_{vendor.id}'
            cache.set(cache_key, metrics, 3600)  # Cache for 1 hour
            
        except Exception as e:
            logger.error(f"Error updating metrics for vendor {vendor.id}: {str(e)}")

@shared_task
def cleanup_old_notifications():
    """Clean up old read notifications to prevent database bloat."""
    try:
        from .models import VendorNotification
        cutoff_date = timezone.now() - timezone.timedelta(days=30)
        
        deleted_count = VendorNotification.objects.filter(
            is_read=True,
            created_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old notifications")
        return f"Cleaned up {deleted_count} old notifications"
    except Exception as e:
        logger.error(f"Error cleaning up notifications: {str(e)}")
        return f"Error: {str(e)}"


@shared_task
def refresh_tor_descriptors():
    """Refresh Tor hidden service descriptors by reloading the service"""
    try:
        logger.info("Starting Tor descriptor refresh...")
        
        result = subprocess.run(
            ['sudo', 'systemctl', 'reload', 'tor@default'],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            logger.info("Tor service reloaded successfully - descriptors will be refreshed")
            
            import time
            time.sleep(5)
            
            log_check = subprocess.run(
                ['sudo', 'tail', '-10', '/var/log/tor/tor.log'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if log_check.returncode == 0 and 'descriptor' in log_check.stdout.lower():
                logger.info("Tor descriptor refresh completed successfully")
                return "Tor descriptors refreshed successfully"
            else:
                logger.warning("Tor reloaded but no descriptor activity detected in logs")
                return "Tor reloaded - descriptor status unclear"
                
        else:
            error_msg = f"Failed to reload Tor service: {result.stderr}"
            logger.error(error_msg)
            return f"Error: {error_msg}"
            
    except subprocess.TimeoutExpired:
        error_msg = "Tor reload command timed out"
        logger.error(error_msg)
        return f"Error: {error_msg}"
        
    except Exception as e:
        error_msg = f"Unexpected error during Tor descriptor refresh: {e}"
        logger.error(error_msg)
        return f"Error: {error_msg}"
