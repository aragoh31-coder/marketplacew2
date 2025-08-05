import hashlib
import secrets
import string

from django.core.cache import cache
from django.utils import timezone


class OrderIDGenerator:
    """Advanced order ID generation with collision detection and tracking references"""

    @staticmethod
    def generate_order_reference(order_data=None):
        """Generate unique order reference ID"""
        timestamp = str(int(timezone.now().timestamp()))
        random_part = "".join(
            secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8)
        )

        if order_data:
            data_hash = hashlib.sha256(str(order_data).encode()).hexdigest()[:4].upper()
            reference = f"ORD-{timestamp[-6:]}-{data_hash}-{random_part}"
        else:
            reference = f"ORD-{timestamp[-6:]}-{random_part}"

        cache_key = f"order_ref:{reference}"
        if cache.get(cache_key):
            return OrderIDGenerator.generate_order_reference(order_data)

        cache.set(cache_key, True, 86400)
        return reference

    @staticmethod
    def generate_tracking_reference(order_reference, vendor_id=None):
        """Generate tracking reference based on order reference"""
        base_data = f"{order_reference}:{vendor_id}:{timezone.now().isoformat()}"
        hash_part = hashlib.sha256(base_data.encode()).hexdigest()[:8].upper()
        random_part = "".join(
            secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6)
        )

        tracking_ref = f"TRK-{hash_part}-{random_part}"

        cache_key = f"tracking_ref:{tracking_ref}"
        if cache.get(cache_key):
            return OrderIDGenerator.generate_tracking_reference(
                order_reference, vendor_id
            )

        cache.set(cache_key, True, 86400)
        return tracking_ref

    @staticmethod
    def generate_dispute_reference(order_reference):
        """Generate dispute reference ID"""
        timestamp = str(int(timezone.now().timestamp()))
        hash_part = (
            hashlib.sha256(f"{order_reference}:{timestamp}".encode())
            .hexdigest()[:6]
            .upper()
        )
        random_part = "".join(
            secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4)
        )

        dispute_ref = f"DSP-{hash_part}-{random_part}"

        cache_key = f"dispute_ref:{dispute_ref}"
        if cache.get(cache_key):
            return OrderIDGenerator.generate_dispute_reference(order_reference)

        cache.set(cache_key, True, 86400)
        return dispute_ref

    @staticmethod
    def validate_reference_format(reference, ref_type="order"):
        """Validate reference ID format"""
        if ref_type == "order":
            return reference.startswith("ORD-") and len(reference) >= 15
        elif ref_type == "tracking":
            return reference.startswith("TRK-") and len(reference) >= 15
        elif ref_type == "dispute":
            return reference.startswith("DSP-") and len(reference) >= 12

        return False

    @staticmethod
    def get_reference_info(reference):
        """Extract information from reference ID"""
        try:
            if reference.startswith("ORD-"):
                parts = reference.split("-")
                if len(parts) >= 3:
                    timestamp_part = parts[1]
                    return {
                        "type": "order",
                        "timestamp_part": timestamp_part,
                        "generated_at": f"Timestamp part: {timestamp_part}",
                    }
            elif reference.startswith("TRK-"):
                return {
                    "type": "tracking",
                    "hash_part": reference.split("-")[1] if "-" in reference else None,
                }
            elif reference.startswith("DSP-"):
                return {
                    "type": "dispute",
                    "hash_part": reference.split("-")[1] if "-" in reference else None,
                }
        except Exception:
            pass

        return {"type": "unknown", "valid": False}
