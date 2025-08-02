import time
import threading
from collections import deque
from django.http import HttpResponse
from django.core.cache import cache
import logging

logger = logging.getLogger('security')

class ResourceProtectionMiddleware:
    """Protect system resources during high-load attacks"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.request_queue = deque(maxlen=1000)
        self.processing_times = deque(maxlen=100)
        self.load_monitor = LoadMonitor()
        self.load_monitor.start()
        
    def __call__(self, request):
        start_time = time.time()
        
        system_load = self.load_monitor.get_current_load()
        
        request_priority = self.calculate_request_priority(request, system_load)
        
        if system_load['level'] == 'critical' and request_priority < 3:
            return HttpResponse("System overloaded", status=503)
        elif system_load['level'] == 'high' and request_priority < 2:
            return HttpResponse("High load - try again", status=503)
        
        try:
            response = self.get_response(request)
            processing_time = (time.time() - start_time) * 1000
            
            self.processing_times.append(processing_time)
            
            if processing_time > self.get_adaptive_timeout(system_load):
                logger.warning(f"Request timeout: {processing_time}ms")
                return HttpResponse("Request timeout", status=408)
            
            return response
            
        except Exception as e:
            logger.error(f"Request processing error: {e}")
            return HttpResponse("Processing error", status=500)
    
    def calculate_request_priority(self, request, system_load):
        """Calculate request priority (1=lowest, 5=highest)"""
        
        priority = 3  # Default priority
        
        if request.path.startswith(('/static/', '/media/', '/favicon.ico')):
            return 5
        
        if request.path in ['/health/', '/status/', '/ping/']:
            return 4
        
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        if any(bot in user_agent for bot in ['python', 'curl', 'bot', 'crawler']):
            priority = 1
        
        if any(path in request.path.lower() for path in ['/admin', '/login', '/auth']):
            priority = 2
        
        if request.path.startswith('/api/'):
            priority = 2
        
        if request.method == 'POST':
            priority -= 1
        
        suspicious_paths = ['wp-admin', 'phpmyadmin', '.env', 'config']
        if any(sus in request.path.lower() for sus in suspicious_paths):
            priority = 1
        
        return max(1, min(5, priority))  # Clamp between 1 and 5
    
    def get_adaptive_timeout(self, system_load):
        """Get adaptive timeout based on system load and recent performance"""
        
        base_timeout = 5000  # 5 seconds
        
        if system_load['level'] == 'critical':
            base_timeout = 1000  # 1 second during critical load
        elif system_load['level'] == 'high':
            base_timeout = 2000  # 2 seconds during high load
        elif system_load['level'] == 'elevated':
            base_timeout = 3000  # 3 seconds during elevated load
        
        if len(self.processing_times) > 10:
            avg_processing_time = sum(self.processing_times) / len(self.processing_times)
            if avg_processing_time > 1000:  # Average > 1 second
                base_timeout = min(base_timeout, avg_processing_time * 1.5)
        
        return base_timeout


class LoadMonitor:
    """Background load monitoring"""
    
    def __init__(self):
        self.current_load = {
            'cpu_percent': 0,
            'memory_percent': 0,
            'connections': 0,
            'level': 'normal',
            'timestamp': time.time()
        }
        self.monitoring = False
        self.thread = None
    
    def start(self):
        """Start background monitoring"""
        if not self.monitoring:
            self.monitoring = True
            self.thread = threading.Thread(target=self._monitor_loop)
            self.thread.daemon = True
            self.thread.start()
    
    def stop(self):
        """Stop monitoring"""
        self.monitoring = False
        if self.thread:
            self.thread.join()
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        while self.monitoring:
            try:
                self._update_load_metrics()
                time.sleep(5)  # Update every 5 seconds
            except Exception as e:
                logger.error(f"Load monitoring error: {e}")
    
    def _update_load_metrics(self):
        """Update current load metrics"""
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            connections = len(psutil.net_connections(kind='inet'))
            
            load_level = self._calculate_load_level(cpu_percent, memory.percent, connections)
            
            self.current_load = {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'connections': connections,
                'level': load_level,
                'timestamp': time.time()
            }
            
            cache.set('system_load_metrics', self.current_load, 30)
            
        except ImportError:
            self.current_load['level'] = 'normal'
    
    def _calculate_load_level(self, cpu_percent, memory_percent, connections):
        """Calculate system load level"""
        
        if cpu_percent > 90 or memory_percent > 95 or connections > 2000:
            return 'critical'
        
        elif cpu_percent > 75 or memory_percent > 85 or connections > 1500:
            return 'high'
        
        elif cpu_percent > 60 or memory_percent > 70 or connections > 1000:
            return 'elevated'
        
        else:
            return 'normal'
    
    def get_current_load(self):
        """Get current load metrics"""
        return self.current_load.copy()


class AdaptiveRateLimiter:
    """Rate limiter that adapts to attack patterns"""
    
    def __init__(self):
        self.base_limits = {
            'requests_per_minute': 20,
            'requests_per_hour': 200,
            'burst_limit': 5
        }
        self.current_limits = self.base_limits.copy()
        self.last_adaptation = time.time()
    
    def check_rate_limit(self, identifier, request_type='normal'):
        """Check if request exceeds adaptive rate limits"""
        
        current_time = time.time()
        
        self._adapt_limits_if_needed()
        
        windows = [
            ('minute', 60, self.current_limits['requests_per_minute']),
            ('hour', 3600, self.current_limits['requests_per_hour']),
            ('burst', 10, self.current_limits['burst_limit'])
        ]
        
        for window_name, duration, limit in windows:
            if self._check_window_limit(identifier, window_name, duration, limit, current_time):
                return False, f"Rate limit exceeded: {window_name}"
        
        return True, "OK"
    
    def _check_window_limit(self, identifier, window_name, duration, limit, current_time):
        """Check specific rate limit window"""
        
        cache_key = f"adaptive_rate:{window_name}:{identifier}"
        timestamps = cache.get(cache_key, [])
        
        timestamps = [t for t in timestamps if current_time - t < duration]
        
        if len(timestamps) >= limit:
            return True
        
        timestamps.append(current_time)
        cache.set(cache_key, timestamps, duration)
        
        return False
    
    def _adapt_limits_if_needed(self):
        """Adapt rate limits based on attack detection"""
        
        current_time = time.time()
        
        if current_time - self.last_adaptation < 60:
            return
        
        self.last_adaptation = current_time
        
        system_load = cache.get('system_load_metrics', {})
        attack_metrics = cache.get('security_metrics_snapshot', {})
        
        under_attack = False
        if attack_metrics:
            block_rate = attack_metrics.get('block_rate_percent', 0)
            requests_per_minute = attack_metrics.get('requests_per_minute', 0)
            
            if block_rate > 50 or requests_per_minute > 100:
                under_attack = True
        
        if under_attack or system_load.get('level') in ['high', 'critical']:
            self.current_limits = {
                'requests_per_minute': 10,  # Reduced from 20
                'requests_per_hour': 100,   # Reduced from 200
                'burst_limit': 3            # Reduced from 5
            }
            logger.info("Rate limits tightened due to attack/high load")
        else:
            if self.current_limits != self.base_limits:
                self.current_limits = self.base_limits.copy()
                logger.info("Rate limits returned to normal")


adaptive_rate_limiter = AdaptiveRateLimiter()
