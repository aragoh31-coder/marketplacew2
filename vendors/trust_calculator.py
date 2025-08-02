from decimal import Decimal
from django.utils import timezone
from django.db.models import Avg, Count, Q
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

class VendorTrustCalculator:
    """Calculate and manage vendor trust levels"""
    
    TRUST_LEVELS = {
        'new': {'min_score': 0, 'max_score': 20, 'label': 'New Vendor'},
        'beginner': {'min_score': 21, 'max_score': 40, 'label': 'Beginner'},
        'regular': {'min_score': 41, 'max_score': 60, 'label': 'Regular'},
        'trusted': {'min_score': 61, 'max_score': 80, 'label': 'Trusted'},
        'premium': {'min_score': 81, 'max_score': 95, 'label': 'Premium'},
        'legendary': {'min_score': 96, 'max_score': 100, 'label': 'Legendary'}
    }
    
    @classmethod
    def calculate_trust_score(cls, vendor):
        """Calculate comprehensive trust score for vendor"""
        try:
            score = 0
            factors = {}
            
            account_age = (timezone.now().date() - vendor.user.date_joined.date()).days
            if account_age >= 365:
                age_score = 15
            elif account_age >= 180:
                age_score = 12
            elif account_age >= 90:
                age_score = 8
            elif account_age >= 30:
                age_score = 5
            else:
                age_score = 0
            
            score += age_score
            factors['account_age'] = {'score': age_score, 'days': account_age}
            
            total_orders = vendor.vendor_orders.count()
            if total_orders > 0:
                completed_orders = vendor.vendor_orders.filter(status='completed').count()
                completion_rate = (completed_orders / total_orders) * 100
                
                if completion_rate >= 98:
                    completion_score = 25
                elif completion_rate >= 95:
                    completion_score = 20
                elif completion_rate >= 90:
                    completion_score = 15
                elif completion_rate >= 80:
                    completion_score = 10
                else:
                    completion_score = 5
            else:
                completion_score = 0
                completion_rate = 0
            
            score += completion_score
            factors['completion_rate'] = {
                'score': completion_score,
                'rate': completion_rate,
                'total_orders': total_orders
            }
            
            if hasattr(vendor, 'feedback_score') and vendor.feedback_score > 0:
                feedback_score = min(20, int(vendor.feedback_score * 4))
            else:
                feedback_score = 0
            
            score += feedback_score
            factors['feedback'] = {'score': feedback_score, 'rating': getattr(vendor, 'feedback_score', 0)}
            
            if total_orders > 0:
                disputed_orders = vendor.vendor_orders.filter(status='disputed').count()
                dispute_rate = (disputed_orders / total_orders) * 100
                
                if dispute_rate <= 1:
                    dispute_score = 15
                elif dispute_rate <= 3:
                    dispute_score = 10
                elif dispute_rate <= 5:
                    dispute_score = 5
                else:
                    dispute_score = 0
            else:
                dispute_score = 15
                dispute_rate = 0
            
            score += dispute_score
            factors['dispute_rate'] = {
                'score': dispute_score,
                'rate': dispute_rate
            }
            
            avg_response_time = cls._calculate_avg_response_time(vendor)
            if avg_response_time <= 2:  # 2 hours
                response_score = 10
            elif avg_response_time <= 6:  # 6 hours
                response_score = 8
            elif avg_response_time <= 24:  # 24 hours
                response_score = 5
            else:
                response_score = 2
            
            score += response_score
            factors['response_time'] = {
                'score': response_score,
                'avg_hours': avg_response_time
            }
            
            last_30_days = timezone.now() - timedelta(days=30)
            recent_orders = vendor.vendor_orders.filter(created_at__gte=last_30_days).count()
            
            if recent_orders >= 50:
                volume_score = 10
            elif recent_orders >= 20:
                volume_score = 8
            elif recent_orders >= 10:
                volume_score = 6
            elif recent_orders >= 5:
                volume_score = 4
            else:
                volume_score = 2
            
            score += volume_score
            factors['volume'] = {
                'score': volume_score,
                'recent_orders': recent_orders
            }
            
            security_score = 0
            if vendor.user.totp_enabled:
                security_score += 2
            if vendor.user.pgp_public_key:
                security_score += 3
            
            score += security_score
            factors['security'] = {
                'score': security_score,
                'totp_enabled': vendor.user.totp_enabled,
                'pgp_enabled': bool(vendor.user.pgp_public_key)
            }
            
            final_score = min(100, max(0, score))
            
            return {
                'trust_score': final_score,
                'trust_level': cls._get_trust_level(final_score),
                'factors': factors,
                'calculated_at': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate trust score for vendor {vendor.id}: {e}")
            return {
                'trust_score': 0,
                'trust_level': 'new',
                'error': str(e)
            }
    
    @classmethod
    def _calculate_avg_response_time(cls, vendor):
        """Calculate average response time in hours"""
        try:
            from messaging.models import Message
            
            recent_messages = Message.objects.filter(
                recipient=vendor.user,
                created_at__gte=timezone.now() - timedelta(days=30)
            ).select_related('conversation')
            
            response_times = []
            for message in recent_messages:
                response = Message.objects.filter(
                    conversation=message.conversation,
                    sender=vendor.user,
                    created_at__gt=message.created_at
                ).first()
                
                if response:
                    response_time = (response.created_at - message.created_at).total_seconds() / 3600
                    response_times.append(response_time)
            
            if response_times:
                return sum(response_times) / len(response_times)
            else:
                return 24  # Default to 24 hours if no data
                
        except Exception:
            return 24
    
    @classmethod
    def _get_trust_level(cls, score):
        """Get trust level based on score"""
        for level, config in cls.TRUST_LEVELS.items():
            if config['min_score'] <= score <= config['max_score']:
                return level
        return 'new'
    
    @classmethod
    def update_vendor_trust(cls, vendor):
        """Update vendor's trust score and level"""
        try:
            trust_data = cls.calculate_trust_score(vendor)
            
            vendor.trust_score = trust_data['trust_score']
            vendor.trust_level = trust_data['trust_level']
            vendor.trust_factors = trust_data.get('factors', {})
            vendor.trust_updated_at = timezone.now()
            vendor.save(update_fields=['trust_score', 'trust_level', 'trust_factors', 'trust_updated_at'])
            
            logger.info(f"Updated trust for vendor {vendor.id}: {trust_data['trust_score']} ({trust_data['trust_level']})")
            
            return trust_data
            
        except Exception as e:
            logger.error(f"Failed to update vendor trust {vendor.id}: {e}")
            return None
    
    @classmethod
    def get_trust_level_info(cls, level):
        """Get information about a trust level"""
        return cls.TRUST_LEVELS.get(level, cls.TRUST_LEVELS['new'])
    
    @classmethod
    def get_all_trust_levels(cls):
        """Get all available trust levels"""
        return cls.TRUST_LEVELS
