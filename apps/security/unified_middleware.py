import time
import hashlib
import json
import threading
from collections import defaultdict, deque
from django.http import HttpResponse
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger('security')

class UnifiedSecurityMiddleware:
    """Consolidated security middleware combining bot detection, rate limiting, and resource protection"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        self.bot_user_agents = [
            r'bot', r'crawler', r'spider', r'scraper', r'curl', r'wget',
            r'python-requests', r'scrapy', r'selenium', r'phantomjs'
        ]
        
        self.suspicious_paths = [
            r'/wp-admin/', r'/admin\.php', r'\.php$', r'\.asp$',
            r'/xmlrpc\.php', r'/wp-login\.php', r'/phpmyadmin/'
        ]
        
        self.request_queue = deque(maxlen=1000)
        self.processing_times = deque(maxlen=100)
        self.load_monitor = LoadMonitor()
        self.load_monitor.start()
        
        self.circuit_fingerprints = defaultdict(list)
        self.attack_patterns = defaultdict(int)
        self.global_metrics = {
            'total_requests': 0,
            'blocked_requests': 0,
            'circuit_count': 0,
            'attack_vectors_detected': set()
        }
        
        self.security_cache = {}
        self.cache_timeout = 300
        
    def __call__(self, request):
        start_time = time.time()
        
        if request.path.startswith('/anti_ddos/'):
            return self.get_response(request)
        
        if request.user.is_authenticated and request.user.is_staff:
            return self.get_response(request)
        
        client_id = self.get_client_identifier(request)
        
        if self.is_private_ip(client_id):
            return self.get_response(request)
        
        rate_limit_result = self.check_rate_limits(client_id, request)
        if not rate_limit_result['allowed']:
            return HttpResponse(f"Rate limit exceeded: {rate_limit_result['reason']}", status=429)
        
        if self.is_bot_request(request):
            logger.warning(f"Bot detected from {client_id}")
            return HttpResponse("Bot traffic not allowed", status=403)
        
        circuit_id = self.get_circuit_fingerprint(request)
        threat_analysis = self.analyze_threat_landscape(request, circuit_id)
        
        if threat_analysis['action'] == 'block':
            self.record_block(request, circuit_id, threat_analysis['reason'])
            return HttpResponse(f"Blocked: {threat_analysis['reason']}", status=403)
        
        system_load = self.load_monitor.get_current_load()
        request_priority = self.calculate_request_priority(request, system_load)
        
        if system_load['level'] == 'critical' and request_priority < 3:
            return HttpResponse("System overloaded", status=503)
        elif system_load['level'] == 'high' and request_priority < 2:
            return HttpResponse("High load - try again", status=503)
        
        try:
            response = self.get_response(request)
            
            response = self.add_security_headers(response)
            
            processing_time = (time.time() - start_time) * 1000
            self.processing_times.append(processing_time)
            
            if processing_time > self.get_adaptive_timeout(system_load):
                logger.warning(f"Request timeout: {processing_time}ms")
                return HttpResponse("Request timeout", status=408)
            
            self.update_behavioral_models(request, circuit_id, response.status_code)
            self.record_performance_metrics(processing_time, threat_analysis['score'])
            
            return response
            
        except Exception as e:
            logger.error(f"Request processing error: {e}")
            return HttpResponse("Processing error", status=500)
    
    def get_client_identifier(self, request):
        """Get client identifier for rate limiting"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')
    
    def is_private_ip(self, ip):
        """Check if IP is private/loopback"""
        if not ip or ip == 'unknown':
            return False
        
        private_ranges = [
            '127.', '10.', '192.168.', '172.16.', '172.17.', '172.18.',
            '172.19.', '172.20.', '172.21.', '172.22.', '172.23.',
            '172.24.', '172.25.', '172.26.', '172.27.', '172.28.',
            '172.29.', '172.30.', '172.31.', '::1', 'localhost'
        ]
        
        return any(ip.startswith(prefix) for prefix in private_ranges)
    
    def check_rate_limits(self, client_id, request):
        """Comprehensive rate limiting with multiple windows"""
        current_time = time.time()
        
        security_config = getattr(settings, 'SECURITY_CONFIG', {})
        rate_limits = security_config.get('RATE_LIMITS', {
            'requests_per_minute': 50,
            'requests_per_hour': 500,
            'burst_limit': 20
        })
        
        windows = [
            ('minute', 60, rate_limits['requests_per_minute']),
            ('hour', 3600, rate_limits['requests_per_hour']),
            ('burst', 10, rate_limits['burst_limit'])
        ]
        
        for window_name, duration, limit in windows:
            cache_key = f"unified_rate:{window_name}:{client_id}"
            timestamps = cache.get(cache_key, [])
            
            timestamps = [t for t in timestamps if current_time - t < duration]
            
            if len(timestamps) >= limit:
                return {'allowed': False, 'reason': f'{window_name} limit exceeded'}
            
            timestamps.append(current_time)
            cache.set(cache_key, timestamps, duration)
        
        return {'allowed': True, 'reason': 'OK'}
    
    def is_bot_request(self, request):
        """Detect bot requests"""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        path = request.path.lower()
        
        if any(bot in user_agent for bot in self.bot_user_agents):
            return True
        
        if any(sus_path in path for sus_path in ['/wp-admin/', '/phpmyadmin/', '.php', '.asp']):
            return True
        
        browser_headers = ['HTTP_ACCEPT', 'HTTP_ACCEPT_LANGUAGE', 'HTTP_ACCEPT_ENCODING']
        missing_headers = sum(1 for header in browser_headers if not request.META.get(header))
        
        return missing_headers >= 2
    
    def get_circuit_fingerprint(self, request):
        """Create circuit fingerprint for Tor tracking"""
        factors = {
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'accept_lang': request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
            'accept_encoding': request.META.get('HTTP_ACCEPT_ENCODING', ''),
            'connection': request.META.get('HTTP_CONNECTION', ''),
            'dnt': request.META.get('HTTP_DNT', ''),
            'accept': request.META.get('HTTP_ACCEPT', ''),
        }
        
        fingerprint_string = '|'.join([f"{k}:{v}" for k, v in factors.items()])
        circuit_hash = hashlib.sha256(fingerprint_string.encode()).hexdigest()[:20]
        
        return circuit_hash
    
    def analyze_threat_landscape(self, request, circuit_id):
        """Comprehensive threat analysis"""
        current_time = time.time()
        analysis = {
            'score': 0,
            'factors': [],
            'action': 'allow',
            'reason': 'clean'
        }
        
        circuit_score = self.analyze_circuit_behavior(circuit_id, current_time)
        analysis['score'] += circuit_score
        if circuit_score > 30:
            analysis['factors'].append(f'circuit_abuse:{circuit_score}')
        
        global_score = self.analyze_global_patterns(request, current_time)
        analysis['score'] += global_score
        if global_score > 25:
            analysis['factors'].append(f'global_pattern:{global_score}')
        
        request_score = self.analyze_request_sophistication(request)
        analysis['score'] += request_score
        if request_score > 20:
            analysis['factors'].append(f'request_pattern:{request_score}')
        
        vector_score = self.analyze_attack_vectors(request, circuit_id)
        analysis['score'] += vector_score
        if vector_score > 15:
            analysis['factors'].append(f'multi_vector:{vector_score}')
        
        pressure_score = self.analyze_resource_pressure()
        analysis['score'] += pressure_score
        if pressure_score > 10:
            analysis['factors'].append(f'resource_pressure:{pressure_score}')
        
        if analysis['score'] >= 80:
            analysis['action'] = 'block'
            analysis['reason'] = f"High threat score: {analysis['score']}"
        elif analysis['score'] >= 60 and pressure_score > 8:
            analysis['action'] = 'block'
            analysis['reason'] = f"High threat under load: {analysis['score']}"
        
        return analysis
    
    def analyze_circuit_behavior(self, circuit_id, current_time):
        """Analyze circuit behavior patterns"""
        cache_key = f"circuit_behavior:{circuit_id}"
        behavior = cache.get(cache_key, {
            'request_times': [],
            'first_seen': current_time,
            'request_count': 0
        })
        
        behavior['request_times'].append(current_time)
        behavior['request_count'] += 1
        
        behavior['request_times'] = [
            t for t in behavior['request_times'] 
            if current_time - t < 600
        ]
        
        score = 0
        
        circuit_age = current_time - behavior['first_seen']
        if circuit_age < 60 and behavior['request_count'] > 20:
            score += 35
        
        recent_requests = len(behavior['request_times'])
        if recent_requests > 30:
            score += 25
        
        recent_burst = sum(1 for t in behavior['request_times'] if current_time - t < 60)
        if recent_burst > 10:
            score += 20
        
        cache.set(cache_key, behavior, 600)
        return min(score, 50)
    
    def analyze_global_patterns(self, request, current_time):
        """Analyze global attack patterns"""
        self.global_metrics['total_requests'] += 1
        
        global_cache_key = "global_request_rate"
        global_requests = cache.get(global_cache_key, [])
        
        global_requests = [t for t in global_requests if current_time - t < 300]
        global_requests.append(current_time)
        
        cache.set(global_cache_key, global_requests, 300)
        
        score = 0
        
        global_rate = len(global_requests) / 300
        if global_rate > 20:
            score += 30
        elif global_rate > 10:
            score += 15
        
        return min(score, 40)
    
    def analyze_request_sophistication(self, request):
        """Analyze request for attack indicators"""
        score = 0
        
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        path = request.path.lower()
        query = request.META.get('QUERY_STRING', '').lower()
        
        bot_patterns = ['python', 'curl', 'wget', 'httpx', 'requests', 'scrapy']
        if any(pattern in user_agent for pattern in bot_patterns):
            score += 30
        
        browser_headers = ['HTTP_ACCEPT', 'HTTP_ACCEPT_LANGUAGE', 'HTTP_ACCEPT_ENCODING']
        missing_headers = sum(1 for header in browser_headers if not request.META.get(header))
        score += missing_headers * 10
        
        attack_patterns = ['admin', 'login', 'wp-', 'phpmyadmin', '.env', 'config']
        if any(pattern in path for pattern in attack_patterns):
            score += 20
        
        sql_patterns = ['union', 'select', 'drop', 'insert', 'delete', '--']
        if any(pattern in query for pattern in sql_patterns):
            score += 25
        
        return min(score, 45)
    
    def analyze_attack_vectors(self, request, circuit_id):
        """Detect multi-vector attacks"""
        cache_key = f"attack_vectors:{circuit_id}"
        vectors = cache.get(cache_key, set())
        
        current_vector = self.classify_attack_vector(request)
        if current_vector:
            vectors.add(current_vector)
            cache.set(cache_key, vectors, 300)
        
        score = 0
        if len(vectors) > 3:
            score += 30
        elif len(vectors) > 1:
            score += 15
        
        return min(score, 35)
    
    def classify_attack_vector(self, request):
        """Classify attack vector type"""
        path = request.path.lower()
        query = request.META.get('QUERY_STRING', '').lower()
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        if any(pattern in path or pattern in query for pattern in ['union', 'select', 'drop']):
            return 'sql_injection'
        
        if '<script' in path or 'javascript:' in path:
            return 'xss'
        
        if '../' in path or '/etc/' in path:
            return 'path_traversal'
        
        if any(bot in user_agent for bot in ['python', 'curl', 'bot']):
            return 'automated_bot'
        
        if '/api/' in path and request.method in ['POST', 'PUT', 'DELETE']:
            return 'api_abuse'
        
        return None
    
    def analyze_resource_pressure(self):
        """Analyze system resource pressure"""
        try:
            import psutil
            
            cpu_percent = psutil.cpu_percent()
            memory_percent = psutil.virtual_memory().percent
            
            score = 0
            
            if cpu_percent > 80:
                score += 15
            elif cpu_percent > 60:
                score += 8
            
            if memory_percent > 85:
                score += 12
            elif memory_percent > 70:
                score += 6
            
            return min(score, 25)
            
        except ImportError:
            return 0
    
    def calculate_request_priority(self, request, system_load):
        """Calculate request priority for resource protection"""
        priority = 3
        
        if request.path.startswith(('/static/', '/media/', '/favicon.ico')):
            return 5
        
        if request.path in ['/health/', '/status/', '/ping/']:
            return 4
        
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        if any(bot in user_agent for bot in ['python', 'curl', 'bot', 'crawler']):
            priority = 1
        
        if any(path in request.path.lower() for path in ['/admin', '/login', '/auth']):
            priority = 2
        
        if request.method == 'POST':
            priority -= 1
        
        return max(1, min(5, priority))
    
    def get_adaptive_timeout(self, system_load):
        """Get adaptive timeout based on system load"""
        base_timeout = 5000
        
        if system_load['level'] == 'critical':
            base_timeout = 1000
        elif system_load['level'] == 'high':
            base_timeout = 2000
        elif system_load['level'] == 'elevated':
            base_timeout = 3000
        
        if len(self.processing_times) > 10:
            avg_processing_time = sum(self.processing_times) / len(self.processing_times)
            if avg_processing_time > 1000:
                base_timeout = min(base_timeout, avg_processing_time * 1.5)
        
        return base_timeout
    
    def add_security_headers(self, response):
        """Add security headers to response"""
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'same-origin'
        response['Content-Security-Policy'] = "default-src 'self'; script-src 'none'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
        
        return response
    
    def record_block(self, request, circuit_id, reason):
        """Record blocked request"""
        self.global_metrics['blocked_requests'] += 1
        
        block_data = {
            'timestamp': time.time(),
            'circuit_id': circuit_id,
            'path': request.path,
            'method': request.method,
            'reason': reason,
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:100],
        }
        
        blocks_key = "recent_blocks"
        recent_blocks = cache.get(blocks_key, [])
        recent_blocks.append(block_data)
        
        if len(recent_blocks) > 1000:
            recent_blocks = recent_blocks[-1000:]
        
        cache.set(blocks_key, recent_blocks, 3600)
        
        logger.warning(f"Unified security block: {reason} | Circuit: {circuit_id[:8]} | Path: {request.path}")
    
    def update_behavioral_models(self, request, circuit_id, status_code):
        """Update behavioral learning models"""
        behavior_key = f"circuit_success:{circuit_id}"
        success_data = cache.get(behavior_key, {'success': 0, 'total': 0})
        
        success_data['total'] += 1
        if status_code < 400:
            success_data['success'] += 1
        
        cache.set(behavior_key, success_data, 300)
    
    def record_performance_metrics(self, processing_time, threat_score):
        """Record performance metrics"""
        metrics = {
            'processing_time': processing_time,
            'threat_score': threat_score,
            'timestamp': time.time()
        }
        
        perf_key = "unified_security_performance"
        perf_data = cache.get(perf_key, [])
        perf_data.append(metrics)
        
        if len(perf_data) > 100:
            perf_data = perf_data[-100:]
        
        cache.set(perf_key, perf_data, 1800)


class LoadMonitor:
    """Background system load monitoring"""
    
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
                time.sleep(5)
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
