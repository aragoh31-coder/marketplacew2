from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from functools import wraps
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

class AdvancedCacheManager:
    """Advanced cache management with analytics and optimization"""
    
    def __init__(self):
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
    
    def get(self, key, default=None, version=None):
        """Enhanced cache get with statistics"""
        try:
            value = cache.get(key, default, version)
            
            if value is not None and value != default:
                self.cache_stats['hits'] += 1
                logger.debug(f"Cache hit: {key}")
            else:
                self.cache_stats['misses'] += 1
                logger.debug(f"Cache miss: {key}")
            
            return value
            
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return default
    
    def set(self, key, value, timeout=None, version=None):
        """Enhanced cache set with statistics"""
        try:
            result = cache.set(key, value, timeout, version)
            self.cache_stats['sets'] += 1
            logger.debug(f"Cache set: {key} (timeout: {timeout})")
            return result
            
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    def delete(self, key, version=None):
        """Enhanced cache delete with statistics"""
        try:
            result = cache.delete(key, version)
            self.cache_stats['deletes'] += 1
            logger.debug(f"Cache delete: {key}")
            return result
            
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    def get_or_set(self, key, default_func, timeout=None, version=None):
        """Get from cache or set using default function"""
        try:
            value = self.get(key, version=version)
            
            if value is None:
                value = default_func()
                self.set(key, value, timeout, version)
            
            return value
            
        except Exception as e:
            logger.error(f"Cache get_or_set error for key {key}: {e}")
            try:
                return default_func()
            except Exception as func_error:
                logger.error(f"Default function error: {func_error}")
                return None
    
    def invalidate_pattern(self, pattern):
        """Invalidate cache keys matching pattern"""
        try:
            if hasattr(cache, 'delete_pattern'):
                return cache.delete_pattern(pattern)
            else:
                logger.warning("Cache backend doesn't support pattern deletion")
                return False
                
        except Exception as e:
            logger.error(f"Cache pattern invalidation error: {e}")
            return False
    
    def get_cache_stats(self):
        """Get cache statistics"""
        total_requests = self.cache_stats['hits'] + self.cache_stats['misses']
        hit_rate = (self.cache_stats['hits'] / total_requests * 100) if total_requests > 0 else 0
        
        return {
            'hits': self.cache_stats['hits'],
            'misses': self.cache_stats['misses'],
            'sets': self.cache_stats['sets'],
            'deletes': self.cache_stats['deletes'],
            'hit_rate': round(hit_rate, 2),
            'total_requests': total_requests
        }
    
    def clear_stats(self):
        """Clear cache statistics"""
        self.cache_stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }

class CacheDecorator:
    """Decorator for automatic caching of function results"""
    
    def __init__(self, timeout=300, key_prefix=None, vary_on=None):
        self.timeout = timeout
        self.key_prefix = key_prefix
        self.vary_on = vary_on or []
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = self._generate_cache_key(func, args, kwargs)
            
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, self.timeout)
            
            return result
        
        return wrapper
    
    def _generate_cache_key(self, func, args, kwargs):
        """Generate cache key from function and arguments"""
        try:
            key_parts = [
                self.key_prefix or func.__name__,
                func.__module__,
            ]
            
            for arg in args:
                if hasattr(arg, 'id'):
                    key_parts.append(f"id:{arg.id}")
                else:
                    key_parts.append(str(arg)[:50])
            
            for key, value in sorted(kwargs.items()):
                if key in self.vary_on:
                    key_parts.append(f"{key}:{value}")
            
            key_string = ":".join(key_parts)
            return hashlib.sha256(key_string.encode()).hexdigest()[:32]
            
        except Exception as e:
            logger.error(f"Failed to generate cache key: {e}")
            return f"{func.__name__}:error"

cache_manager = AdvancedCacheManager()
