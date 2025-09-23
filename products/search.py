from django.contrib.postgres.search import (
    SearchVector, SearchQuery, SearchRank, TrigramSimilarity
)
from django.db.models import Q
from django.core.cache import cache
from django.utils import timezone
from products.models import Product
import hashlib
import random
import logging

logger = logging.getLogger('products.search')


class AdvancedProductSearch:
    """Privacy-preserving product search with advanced filtering"""
    
    def __init__(self):
        self.min_results = 20  # Always return at least 20 results for privacy
        self.dummy_query_probability = 0.15  # 15% chance of dummy query
        
    def search_products(self, query, filters=None, user=None):
        """
        Advanced product search with PostgreSQL FTS
        
        Args:
            query: Search query string
            filters: Dict of filters (price_range, vendor_rating, shipping_from, etc.)
            user: Current user (for saved searches)
        """
        
        # Add dummy queries for obfuscation
        if random.random() < self.dummy_query_probability:
            self._generate_dummy_query()
        
        # Clean and prepare query
        cleaned_query = self._sanitize_query(query)
        
        # Build base queryset
        queryset = Product.objects.filter(is_available=True)
        
        if cleaned_query:
            # Create search vector for full-text search
            search_vector = SearchVector(
                'name', weight='A'
            ) + SearchVector(
                'description', weight='B'
            ) + SearchVector(
                'category__name', weight='C'
            )
            
            search_query = SearchQuery(cleaned_query)
            
            # Add trigram similarity for fuzzy matching
            queryset = queryset.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query),
                similarity=TrigramSimilarity('name', cleaned_query)
            ).filter(
                Q(search=search_query) | Q(similarity__gt=0.3)
            ).order_by('-rank', '-similarity')
        
        # Apply filters
        queryset = self._apply_filters(queryset, filters)
        
        # Add result obfuscation
        results = self._obfuscate_results(queryset, user)
        
        # Save search for user (encrypted)
        if user and user.is_authenticated:
            self._save_search(user, query, filters)
        
        return results
    
    def _apply_filters(self, queryset, filters):
        """Apply advanced filters to search results"""
        if not filters:
            return queryset
        
        # Price range filter
        if 'price_min' in filters and 'price_max' in filters:
            currency = filters.get('currency', 'btc')
            price_field = f'price_{currency}'
            queryset = queryset.filter(
                **{f'{price_field}__gte': filters['price_min'],
                   f'{price_field}__lte': filters['price_max']}
            )
        
        # Vendor rating filter
        if 'vendor_rating' in filters:
            queryset = queryset.filter(vendor__rating__gte=filters['vendor_rating'])
        
        # Shipping origin filter
        if 'shipping_from' in filters:
            queryset = queryset.filter(vendor__shipping_from__icontains=filters['shipping_from'])
        
        # FE allowed filter
        if 'fe_allowed' in filters and filters['fe_allowed']:
            queryset = queryset.filter(
                vendor__trust_level__in=['VERIFIED', 'PREMIUM'],
                vendor__bond_paid=True
            )
        
        # Product type filter
        if 'product_type' in filters:
            queryset = queryset.filter(product_type=filters['product_type'])
        
        # In stock only
        if filters.get('in_stock_only', False):
            queryset = queryset.filter(stock_quantity__gt=0)
        
        return queryset
    
    def _obfuscate_results(self, queryset, user):
        """Add privacy-preserving obfuscation to results"""
        results = list(queryset[:100])  # Limit to 100 real results
        
        # Always return minimum number of results
        if len(results) < self.min_results:
            # Pad with random products (marked as dummy)
            dummy_products = Product.objects.filter(
                is_available=True
            ).exclude(
                id__in=[r.id for r in results]
            ).order_by('?')[:self.min_results - len(results)]
            
            for dummy in dummy_products:
                dummy._is_dummy = True
                results.append(dummy)
        
        # Shuffle results slightly to prevent timing analysis
        if len(results) > 10:
            # Shuffle within groups of 10 to maintain relevance
            for i in range(0, len(results), 10):
                group = results[i:i+10]
                random.shuffle(group)
                results[i:i+10] = group
        
        return results
    
    def _sanitize_query(self, query):
        """Sanitize search query for security"""
        if not query:
            return ''
        
        # Remove special characters that could be used for injection
        forbidden_chars = ['<', '>', '"', "'", '\\', '\x00', '\n', '\r', '\t']
        for char in forbidden_chars:
            query = query.replace(char, '')
        
        # Limit query length
        return query[:100]
    
    def _generate_dummy_query(self):
        """Generate dummy search query for obfuscation"""
        dummy_queries = [
            'electronics', 'gift cards', 'digital goods', 'software',
            'accounts', 'documents', 'services', 'guides'
        ]
        
        dummy = random.choice(dummy_queries)
        
        # Log as dummy for statistics (but don't track details)
        logger.debug(f"Dummy query generated for obfuscation")
        
        # Execute dummy search but don't return results
        Product.objects.filter(
            Q(name__icontains=dummy) | Q(description__icontains=dummy)
        )[:5]
    
    def _save_search(self, user, query, filters):
        """Save user search (encrypted) for alerts"""
        from .models import SavedSearch
        
        # Hash the search for privacy
        search_hash = hashlib.sha256(f"{user.id}{query}{filters}".encode()).hexdigest()
        
        # Check if already saved
        if SavedSearch.objects.filter(user=user, search_hash=search_hash).exists():
            return
        
        SavedSearch.objects.create(
            user=user,
            search_hash=search_hash,
            encrypted_query=self._encrypt_search_data(query, filters),
            alert_enabled=False
        )
    
    def _encrypt_search_data(self, query, filters):
        """Encrypt search data for storage"""
        from config.security_config import SECRET_MANAGER
        import json
        
        data = {
            'query': query,
            'filters': filters,
            'timestamp': timezone.now().isoformat()
        }
        
        return SECRET_MANAGER.encrypt_sensitive_data(json.dumps(data))
    
    def get_trending_products(self, limit=10):
        """Get trending products with privacy preservation"""
        # Use cached trending to prevent correlation
        cache_key = 'trending_products_hourly'
        cached = cache.get(cache_key)
        
        if cached:
            return cached
        
        # Calculate trending based on recent orders (fuzzy)
        from django.db.models import Count
        
        # Get products ordered in last 7 days
        week_ago = timezone.now() - timezone.timedelta(days=7)
        
        trending = Product.objects.filter(
            is_available=True,
            orderitem__order__created_at__gte=week_ago
        ).annotate(
            order_count=Count('orderitem')
        ).order_by('-order_count')[:limit * 2]  # Get extra for randomization
        
        # Randomize order slightly for privacy
        trending_list = list(trending)
        random.shuffle(trending_list)
        results = trending_list[:limit]
        
        # Cache for 1 hour
        cache.set(cache_key, results, 3600)
        
        return results
    
    def get_popular_tags(self):
        """Get popular product tags with fuzzing"""
        from .models import ProductTag
        
        cache_key = 'popular_tags_daily'
        cached = cache.get(cache_key)
        
        if cached:
            return cached
        
        tags = ProductTag.objects.filter(
            products__is_available=True
        ).annotate(
            product_count=Count('products')
        ).order_by('-product_count')[:20]
        
        # Add some randomization
        tags_list = list(tags)
        random.shuffle(tags_list)
        
        # Cache for 24 hours
        cache.set(cache_key, tags_list[:15], 86400)
        
        return tags_list[:15]


class SavedSearch(PrivacyModel):
    """Saved searches with alerts"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_searches')
    search_hash = models.CharField(max_length=64, db_index=True)
    encrypted_query = models.TextField()
    alert_enabled = models.BooleanField(default=False)
    last_alerted = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['user', 'search_hash']
        indexes = [
            models.Index(fields=['user', 'alert_enabled']),
        ]


class ProductTag(PrivacyModel):
    """Tags for better product categorization"""
    
    name = models.CharField(max_length=50, unique=True)
    products = models.ManyToManyField(Product, related_name='tags')
    
    def __str__(self):
        return self.name