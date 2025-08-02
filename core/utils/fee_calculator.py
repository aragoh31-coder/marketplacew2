from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class MarketplaceFeeCalculator:
    """Centralized fee calculation utilities for the marketplace"""
    
    DEFAULT_FEES = {
        'marketplace_fee_percentage': Decimal('2.5'),
        'payment_processing_fee': Decimal('0.5'),
        'withdrawal_fee_btc': Decimal('0.0005'),
        'withdrawal_fee_xmr': Decimal('0.01'),
        'dispute_fee': Decimal('0.001'),
        'vendor_listing_fee': Decimal('0.0001'),
        'premium_listing_multiplier': Decimal('2.0'),
    }
    
    @classmethod
    def get_fee_rate(cls, fee_type):
        """Get fee rate from settings or use default"""
        try:
            return getattr(settings, f'MARKETPLACE_{fee_type.upper()}', cls.DEFAULT_FEES.get(fee_type, Decimal('0')))
        except Exception as e:
            logger.warning(f"Failed to get fee rate for {fee_type}: {e}")
            return cls.DEFAULT_FEES.get(fee_type, Decimal('0'))
    
    @classmethod
    def calculate_marketplace_fee(cls, order_amount, vendor_tier='standard'):
        """Calculate marketplace fee for an order"""
        try:
            base_rate = cls.get_fee_rate('marketplace_fee_percentage')
            
            tier_multipliers = {
                'new': Decimal('1.2'),
                'standard': Decimal('1.0'),
                'trusted': Decimal('0.8'),
                'premium': Decimal('0.6'),
                'legendary': Decimal('0.5')
            }
            
            multiplier = tier_multipliers.get(vendor_tier, Decimal('1.0'))
            fee_rate = base_rate * multiplier / 100
            
            fee_amount = (order_amount * fee_rate).quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)
            
            return {
                'fee_amount': fee_amount,
                'fee_rate': fee_rate * 100,
                'base_rate': base_rate,
                'tier_multiplier': multiplier,
                'vendor_tier': vendor_tier
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate marketplace fee: {e}")
            return {
                'fee_amount': Decimal('0'),
                'fee_rate': Decimal('0'),
                'error': str(e)
            }
    
    @classmethod
    def calculate_withdrawal_fee(cls, amount, currency='BTC'):
        """Calculate withdrawal fee"""
        try:
            if currency.upper() == 'BTC':
                base_fee = cls.get_fee_rate('withdrawal_fee_btc')
            elif currency.upper() == 'XMR':
                base_fee = cls.get_fee_rate('withdrawal_fee_xmr')
            else:
                base_fee = Decimal('0.001')
            
            percentage_fee = amount * Decimal('0.001')
            
            final_fee = max(base_fee, percentage_fee)
            
            max_fee = amount * Decimal('0.05')
            final_fee = min(final_fee, max_fee)
            
            return {
                'fee_amount': final_fee.quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP),
                'base_fee': base_fee,
                'percentage_fee': percentage_fee,
                'currency': currency.upper()
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate withdrawal fee: {e}")
            return {
                'fee_amount': Decimal('0.001'),
                'error': str(e)
            }
    
    @classmethod
    def calculate_listing_fee(cls, product_data, is_premium=False):
        """Calculate product listing fee"""
        try:
            base_fee = cls.get_fee_rate('vendor_listing_fee')
            
            if is_premium:
                multiplier = cls.get_fee_rate('premium_listing_multiplier')
                fee = base_fee * multiplier
            else:
                fee = base_fee
            
            category_multipliers = {
                'digital': Decimal('0.5'),
                'physical': Decimal('1.0'),
                'services': Decimal('0.8'),
                'restricted': Decimal('2.0')
            }
            
            category = product_data.get('category', 'physical')
            category_multiplier = category_multipliers.get(category, Decimal('1.0'))
            
            final_fee = (fee * category_multiplier).quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP)
            
            return {
                'fee_amount': final_fee,
                'base_fee': base_fee,
                'is_premium': is_premium,
                'category_multiplier': category_multiplier,
                'category': category
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate listing fee: {e}")
            return {
                'fee_amount': cls.DEFAULT_FEES['vendor_listing_fee'],
                'error': str(e)
            }
    
    @classmethod
    def calculate_dispute_fee(cls, order_amount):
        """Calculate dispute processing fee"""
        try:
            base_fee = cls.get_fee_rate('dispute_fee')
            percentage_fee = order_amount * Decimal('0.01')
            
            dispute_fee = max(base_fee, percentage_fee)
            
            max_dispute_fee = order_amount * Decimal('0.1')
            dispute_fee = min(dispute_fee, max_dispute_fee)
            
            return {
                'fee_amount': dispute_fee.quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP),
                'base_fee': base_fee,
                'percentage_fee': percentage_fee,
                'max_fee': max_dispute_fee
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate dispute fee: {e}")
            return {
                'fee_amount': cls.DEFAULT_FEES['dispute_fee'],
                'error': str(e)
            }
    
    @classmethod
    def calculate_total_fees(cls, order_amount, vendor_tier='standard', currency='BTC', include_withdrawal=False):
        """Calculate total fees for an order"""
        try:
            marketplace_fee = cls.calculate_marketplace_fee(order_amount, vendor_tier)
            payment_fee = order_amount * (cls.get_fee_rate('payment_processing_fee') / 100)
            
            total_fees = marketplace_fee['fee_amount'] + payment_fee
            
            if include_withdrawal:
                withdrawal_fee = cls.calculate_withdrawal_fee(order_amount, currency)
                total_fees += withdrawal_fee['fee_amount']
            
            return {
                'total_fees': total_fees.quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP),
                'marketplace_fee': marketplace_fee['fee_amount'],
                'payment_fee': payment_fee.quantize(Decimal('0.00000001'), rounding=ROUND_HALF_UP),
                'withdrawal_fee': withdrawal_fee['fee_amount'] if include_withdrawal else Decimal('0'),
                'fee_breakdown': {
                    'marketplace': marketplace_fee,
                    'payment': {'fee_amount': payment_fee, 'rate': cls.get_fee_rate('payment_processing_fee')},
                    'withdrawal': withdrawal_fee if include_withdrawal else None
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate total fees: {e}")
            return {
                'total_fees': Decimal('0'),
                'error': str(e)
            }
    
    @classmethod
    def get_fee_schedule(cls):
        """Get complete fee schedule for display"""
        return {
            'marketplace_fees': {
                'new_vendor': f"{cls.get_fee_rate('marketplace_fee_percentage') * Decimal('1.2')}%",
                'standard_vendor': f"{cls.get_fee_rate('marketplace_fee_percentage')}%",
                'trusted_vendor': f"{cls.get_fee_rate('marketplace_fee_percentage') * Decimal('0.8')}%",
                'premium_vendor': f"{cls.get_fee_rate('marketplace_fee_percentage') * Decimal('0.6')}%",
                'legendary_vendor': f"{cls.get_fee_rate('marketplace_fee_percentage') * Decimal('0.5')}%"
            },
            'withdrawal_fees': {
                'btc': f"{cls.get_fee_rate('withdrawal_fee_btc')} BTC minimum",
                'xmr': f"{cls.get_fee_rate('withdrawal_fee_xmr')} XMR minimum"
            },
            'listing_fees': {
                'standard': f"{cls.get_fee_rate('vendor_listing_fee')} BTC",
                'premium': f"{cls.get_fee_rate('vendor_listing_fee') * cls.get_fee_rate('premium_listing_multiplier')} BTC"
            },
            'other_fees': {
                'payment_processing': f"{cls.get_fee_rate('payment_processing_fee')}%",
                'dispute_processing': f"{cls.get_fee_rate('dispute_fee')} BTC minimum"
            }
        }
