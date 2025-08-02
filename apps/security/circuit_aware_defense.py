import time
import hashlib
import json
from collections import defaultdict
from django.core.cache import cache
from django.http import HttpResponse
from django.conf import settings
import logging

logger = logging.getLogger('security')

class CircuitAwareDefense:
    """Advanced defense against circuit rotation and multi-vector attacks"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.circuit_fingerprints = defaultdict(list)
        self.attack_patterns = defaultdict(int)
        self.global_metrics = {
            'total_requests': 0,
            'blocked_requests': 0,
            'circuit_count': 0,
            'attack_vectors_detected': set()
        }
        
    def __call__(self, request):
        start_time = time.time()
        
        if request.path.startswith('/anti_ddos/'):
            return self.get_response(request)
        
        circuit_id = self.get_circuit_fingerprint(request)
        threat_analysis = self.analyze_threat_landscape(request, circuit_id)
        
        if threat_analysis['action'] == 'block':
            self.record_block(request, circuit_id, threat_analysis['reason'])
            return HttpResponse(f"Blocked: {threat_analysis['reason']}", status=403)
        
        response = self.get_response(request)
        
        self.update_behavioral_models(request, circuit_id, response.status_code)
        
        processing_time = (time.time() - start_time) * 1000
        self.record_performance_metrics(processing_time, threat_analysis['score'])
        
        return response
    
    def get_circuit_fingerprint(self, request):
        """Create sophisticated circuit fingerprint to track across IP rotations"""
        
        factors = {
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'accept_lang': request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
            'accept_encoding': request.META.get('HTTP_ACCEPT_ENCODING', ''),
            'connection': request.META.get('HTTP_CONNECTION', ''),
            'dnt': request.META.get('HTTP_DNT', ''),
            'accept': request.META.get('HTTP_ACCEPT', ''),
            'x_forwarded': request.META.get('HTTP_X_FORWARDED_FOR', ''),
            'via': request.META.get('HTTP_VIA', ''),
        }
        
        fingerprint_string = '|'.join([f"{k}:{v}" for k, v in factors.items()])
        circuit_hash = hashlib.sha256(fingerprint_string.encode()).hexdigest()[:20]
        
        return circuit_hash
    
    def analyze_threat_landscape(self, request, circuit_id):
        """Comprehensive threat analysis using multiple detection layers"""
        
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
        
        if analysis['score'] >= 80:  # Very high threat (raised from 70)
            analysis['action'] = 'block'
            analysis['reason'] = f"High threat score: {analysis['score']}"
        elif analysis['score'] >= 60:  # High threat during pressure (raised from 50)
            if pressure_score > 8:  # Under load (raised from 5)
                analysis['action'] = 'block'
                analysis['reason'] = f"High threat under load: {analysis['score']}"
        
        return analysis
    
    def analyze_circuit_behavior(self, circuit_id, current_time):
        """Analyze behavior patterns for this specific circuit"""
        
        cache_key = f"circuit_behavior:{circuit_id}"
        behavior = cache.get(cache_key, {
            'request_times': [],
            'paths_accessed': set(),
            'user_agents': set(),
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
        if circuit_age < 60 and behavior['request_count'] > 20:  # 20+ requests in first minute
            score += 35
        
        recent_requests = len(behavior['request_times'])
        if recent_requests > 30:  # More than 30 requests in 10 minutes
            score += 25
        
        recent_burst = sum(1 for t in behavior['request_times'] if current_time - t < 60)
        if recent_burst > 10:  # More than 10 requests per minute
            score += 20
        
        cache.set(cache_key, behavior, 600)
        
        return min(score, 50)  # Cap at 50 points
    
    def analyze_global_patterns(self, request, current_time):
        """Detect global attack patterns across all circuits"""
        
        self.global_metrics['total_requests'] += 1
        
        global_cache_key = "global_request_rate"
        global_requests = cache.get(global_cache_key, [])
        
        global_requests = [t for t in global_requests if current_time - t < 300]
        global_requests.append(current_time)
        
        cache.set(global_cache_key, global_requests, 300)
        
        score = 0
        
        global_rate = len(global_requests) / 300  # Requests per second
        if global_rate > 20:  # More than 20 RPS = likely attack
            score += 30
        elif global_rate > 10:  # More than 10 RPS = elevated
            score += 15
        
        circuit_cache_key = "active_circuits_count"
        circuit_count = cache.get(circuit_cache_key, 0)
        if circuit_count > 50:  # More than 50 active circuits
            score += 25
        
        return min(score, 40)  # Cap at 40 points
    
    def analyze_request_sophistication(self, request):
        """Analyze individual request for attack indicators"""
        
        score = 0
        
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        path = request.path.lower()
        
        bot_patterns = ['python', 'curl', 'wget', 'httpx', 'requests', 'scrapy']
        if any(pattern in user_agent for pattern in bot_patterns):
            score += 30
        
        missing_headers = 0
        browser_headers = ['HTTP_ACCEPT', 'HTTP_ACCEPT_LANGUAGE', 'HTTP_ACCEPT_ENCODING']
        for header in browser_headers:
            if not request.META.get(header):
                missing_headers += 1
        
        score += missing_headers * 10
        
        attack_patterns = [
            'admin', 'login', 'wp-', 'phpmyadmin', '.env', 'config',
            'backup', 'test', 'debug', 'api', 'graphql'
        ]
        
        if any(pattern in path for pattern in attack_patterns):
            score += 20
        
        query_string = request.META.get('QUERY_STRING', '').lower()
        sql_patterns = ['union', 'select', 'drop', 'insert', 'delete', '--']
        if any(pattern in query_string for pattern in sql_patterns):
            score += 25
        
        return min(score, 45)  # Cap at 45 points
    
    def analyze_attack_vectors(self, request, circuit_id):
        """Detect multi-vector attack patterns"""
        
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
        
        high_risk_vectors = ['sql_injection', 'xss', 'path_traversal', 'api_abuse']
        if any(vector in vectors for vector in high_risk_vectors):
            score += 20
        
        return min(score, 35)  # Cap at 35 points
    
    def classify_attack_vector(self, request):
        """Classify the type of attack vector"""
        
        path = request.path.lower()
        query = request.META.get('QUERY_STRING', '').lower()
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        sql_patterns = ['union', 'select', 'drop', 'insert', 'delete', '--', ';']
        if any(pattern in path or pattern in query for pattern in sql_patterns):
            return 'sql_injection'
        
        if '<script' in path or 'javascript:' in path or 'alert(' in query:
            return 'xss'
        
        if '../' in path or '..\\' in path or '/etc/' in path:
            return 'path_traversal'
        
        if any(bot in user_agent for bot in ['python', 'curl', 'bot', 'crawler']):
            return 'automated_bot'
        
        if '/api/' in path and request.method in ['POST', 'PUT', 'DELETE']:
            return 'api_abuse'
        
        if any(admin in path for admin in ['/admin', '/wp-admin', '/management']):
            return 'admin_probe'
        
        return None
    
    def analyze_resource_pressure(self):
        """Factor in current system resource pressure"""
        
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
            
            connections = len(psutil.net_connections(kind='inet'))
            if connections > 1000:
                score += 10
            
            return min(score, 25)  # Cap at 25 points
            
        except ImportError:
            return 0
    
    def record_block(self, request, circuit_id, reason):
        """Record blocked request for learning"""
        
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
        
        logger.warning(f"Circuit defense block: {reason} | Circuit: {circuit_id[:8]} | Path: {request.path}")
    
    def update_behavioral_models(self, request, circuit_id, status_code):
        """Update behavioral learning models"""
        
        behavior_key = f"circuit_success:{circuit_id}"
        success_data = cache.get(behavior_key, {'success': 0, 'total': 0})
        
        success_data['total'] += 1
        if status_code < 400:
            success_data['success'] += 1
        
        cache.set(behavior_key, success_data, 300)
        
        if success_data['total'] > 10:
            success_rate = success_data['success'] / success_data['total']
            if success_rate < 0.3:  # Less than 30% success rate
                suspicious_key = f"suspicious_circuit:{circuit_id}"
                cache.set(suspicious_key, True, 600)
    
    def record_performance_metrics(self, processing_time, threat_score):
        """Track performance impact of security processing"""
        
        metrics = {
            'processing_time': processing_time,
            'threat_score': threat_score,
            'timestamp': time.time()
        }
        
        perf_key = "security_performance_metrics"
        perf_data = cache.get(perf_key, [])
        perf_data.append(metrics)
        
        if len(perf_data) > 100:
            perf_data = perf_data[-100:]
        
        cache.set(perf_key, perf_data, 1800)
