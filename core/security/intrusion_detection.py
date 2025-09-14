import time
import hashlib
import json
import re
from collections import defaultdict, deque
from datetime import datetime, timedelta
from django.core.cache import cache
from django.conf import settings
from django.core.mail import send_mail
from config.security_config import SECRET_MANAGER
import logging

logger = logging.getLogger('security.ids')


class IntrusionDetectionSystem:
    """
    Enterprise-grade Intrusion Detection System (IDS)
    - Real-time threat detection and response
    - Pattern analysis and behavioral monitoring
    - Automated response and alerting
    - Privacy-preserving analytics for Tor compatibility
    """
    
    def __init__(self):
        self.threat_patterns = self._load_threat_patterns()
        self.anomaly_thresholds = {
            'login_failures': 5,
            'rapid_requests': 100,
            'unusual_user_agent': 10,
            'form_spam': 20,
            'payload_injection': 1,
            'directory_traversal': 1,
            'file_upload_abuse': 5,
            'session_anomaly': 3,
        }
        
        self.time_windows = {
            'short': 300,    # 5 minutes
            'medium': 1800,  # 30 minutes  
            'long': 3600,    # 1 hour
        }
        
        self.alert_levels = {
            'LOW': 1,
            'MEDIUM': 2,
            'HIGH': 3,
            'CRITICAL': 4
        }
    
    def _load_threat_patterns(self):
        """Load known attack patterns"""
        return {
            'sql_injection': [
                r'(\bunion\b.*\bselect\b)',
                r'(\bor\b.*=.*\bor\b)',
                r'(\bselect\b.*\bfrom\b)',
                r'(\binsert\b.*\binto\b)',
                r'(\bdelete\b.*\bfrom\b)',
                r'(\bdrop\b.*\btable\b)',
                r'(\bexec\b.*\bxp_)',
                r'(\bsp_executesql\b)',
                r'(\'.*;\s*drop\b)',
                r'(\b0x[0-9a-f]+)',
            ],
            
            'xss': [
                r'(<script[^>]*>.*?</script>)',
                r'(javascript:)',
                r'(vbscript:)',
                r'(onload\s*=)',
                r'(onerror\s*=)',
                r'(onclick\s*=)',
                r'(onmouseover\s*=)',
                r'(<iframe[^>]*>)',
                r'(<object[^>]*>)',
                r'(<embed[^>]*>)',
                r'(eval\s*\()',
                r'(document\.cookie)',
            ],
            
            'command_injection': [
                r'(;\s*cat\b)',
                r'(;\s*ls\b)',
                r'(;\s*id\b)',
                r'(;\s*pwd\b)',
                r'(;\s*whoami\b)',
                r'(\bwget\b)',
                r'(\bcurl\b)',
                r'(\bnc\b.*-l)',
                r'(/bin/bash)',
                r'(/bin/sh)',
                r'(\$\(.*\))',
                r'(`.*`)',
            ],
            
            'directory_traversal': [
                r'(\.\./)|(\.\.\\\\)',
                r'(%2e%2e%2f)|(%2e%2e%5c)',
                r'(\.\./.*\.\./)',
                r'(/etc/passwd)',
                r'(/etc/shadow)',
                r'(/windows/system32)',
                r'(\.\.%2f)',
                r'(%252e%252e)',
            ],
            
            'file_inclusion': [
                r'(\binclude\b.*\.php)',
                r'(\brequire\b.*\.php)',
                r'(php://filter)',
                r'(php://input)',
                r'(data://text)',
                r'(file://)',
                r'(\bftp://)',
            ],
            
            'payload_patterns': [
                r'(<\?php)',
                r'(<%.*%>)',
                r'(\${.*})',
                r'(\#\{.*\})',
                r'(\beval\b)',
                r'(\bexec\b)',
                r'(\bsystem\b)',
                r'(\bshell_exec\b)',
            ]
        }
    
    def analyze_request(self, request):
        """Analyze incoming request for threats"""
        threat_score = 0
        threats_detected = []
        
        # Get client identifier for tracking
        client_id = self._get_client_identifier(request)
        
        # Analyze different aspects of the request
        threat_score += self._analyze_payload_patterns(request, threats_detected)
        threat_score += self._analyze_request_frequency(request, client_id, threats_detected)
        threat_score += self._analyze_user_agent(request, client_id, threats_detected)
        threat_score += self._analyze_session_behavior(request, client_id, threats_detected)
        
        # Determine alert level
        alert_level = self._calculate_alert_level(threat_score)
        
        # Log the analysis
        self._log_threat_analysis(request, client_id, threat_score, threats_detected, alert_level)
        
        # Handle high-severity threats
        if alert_level >= self.alert_levels['HIGH']:
            self._handle_high_severity_threat(request, client_id, threats_detected, threat_score)
        
        return {
            'threat_score': threat_score,
            'threats_detected': threats_detected,
            'alert_level': alert_level,
            'blocked': alert_level >= self.alert_levels['CRITICAL']
        }
    
    def _analyze_payload_patterns(self, request, threats_detected):
        """Analyze request payloads for malicious patterns"""
        score = 0
        
        # Get all request data
        request_data = []
        
        # POST data
        if hasattr(request, 'POST') and request.POST:
            request_data.extend([str(k) + str(v) for k, v in request.POST.items()])
        
        # GET parameters
        if hasattr(request, 'GET') and request.GET:
            request_data.extend([str(k) + str(v) for k, v in request.GET.items()])
        
        # Headers
        for header, value in request.META.items():
            if header.startswith('HTTP_'):
                request_data.append(str(value))
        
        # Path
        request_data.append(request.path)
        
        # Analyze each piece of data
        for data in request_data:
            data_lower = data.lower()
            
            for threat_type, patterns in self.threat_patterns.items():
                for pattern in patterns:
                    if re.search(pattern, data_lower, re.IGNORECASE):
                        score += 10
                        threats_detected.append({
                            'type': threat_type,
                            'pattern': pattern,
                            'data_sample': data[:100]  # First 100 chars only
                        })
                        logger.warning(f"Threat pattern detected: {threat_type} - {pattern}")
        
        return score
    
    def _analyze_request_frequency(self, request, client_id, threats_detected):
        """Analyze request frequency for DDoS/brute force attacks"""
        score = 0
        current_time = time.time()
        
        # Track requests per time window
        for window_name, window_size in self.time_windows.items():
            cache_key = f"ids_freq:{window_name}:{client_id}"
            requests = cache.get(cache_key, [])
            
            # Remove old requests
            requests = [req_time for req_time in requests if current_time - req_time < window_size]
            
            # Add current request
            requests.append(current_time)
            
            # Check thresholds
            if window_name == 'short' and len(requests) > 60:  # 60 requests per 5 minutes
                score += 20
                threats_detected.append({
                    'type': 'rapid_requests',
                    'window': window_name,
                    'count': len(requests)
                })
            elif window_name == 'medium' and len(requests) > 200:  # 200 requests per 30 minutes
                score += 15
                threats_detected.append({
                    'type': 'sustained_attack',
                    'window': window_name,
                    'count': len(requests)
                })
            elif window_name == 'long' and len(requests) > 500:  # 500 requests per hour
                score += 25
                threats_detected.append({
                    'type': 'volume_attack',
                    'window': window_name,
                    'count': len(requests)
                })
            
            # Store updated list
            cache.set(cache_key, requests, window_size)
        
        return score
    
    def _analyze_user_agent(self, request, client_id, threats_detected):
        """Analyze user agent for suspicious patterns"""
        score = 0
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        if not user_agent:
            score += 5
            threats_detected.append({'type': 'missing_user_agent'})
            return score
        
        # Suspicious user agents
        suspicious_ua_patterns = [
            r'bot', r'crawler', r'spider', r'scraper', r'curl', r'wget',
            r'python', r'java', r'perl', r'ruby', r'php', r'scanner',
            r'exploit', r'attack', r'hack', r'sql', r'injection',
            r'nikto', r'sqlmap', r'nessus', r'openvas', r'w3af'
        ]
        
        for pattern in suspicious_ua_patterns:
            if re.search(pattern, user_agent):
                score += 8
                threats_detected.append({
                    'type': 'suspicious_user_agent',
                    'pattern': pattern,
                    'user_agent_sample': user_agent[:50]
                })
        
        # Check for user agent switching
        cache_key = f"ids_ua:{client_id}"
        previous_ua_hash = cache.get(cache_key)
        current_ua_hash = hashlib.md5(user_agent.encode()).hexdigest()
        
        if previous_ua_hash and previous_ua_hash != current_ua_hash:
            score += 10
            threats_detected.append({
                'type': 'user_agent_switching',
                'previous_hash': previous_ua_hash[:8],
                'current_hash': current_ua_hash[:8]
            })
        
        cache.set(cache_key, current_ua_hash, 3600)
        
        return score
    
    def _analyze_session_behavior(self, request, client_id, threats_detected):
        """Analyze session behavior for anomalies"""
        score = 0
        
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return score
        
        user_id = request.user.id
        cache_key = f"ids_session_behavior:{user_id}"
        
        # Track behavioral metrics
        behavior_data = cache.get(cache_key, {
            'login_times': [],
            'page_views': defaultdict(int),
            'form_submissions': 0,
            'failed_actions': 0,
            'last_activity': None
        })
        
        current_time = time.time()
        
        # Check for rapid form submissions
        if request.method == 'POST':
            behavior_data['form_submissions'] += 1
            if behavior_data['form_submissions'] > 20:  # 20 form submissions per session
                score += 15
                threats_detected.append({
                    'type': 'excessive_form_submissions',
                    'count': behavior_data['form_submissions']
                })
        
        # Track page access patterns
        behavior_data['page_views'][request.path] += 1
        if behavior_data['page_views'][request.path] > 50:  # Same page 50+ times
            score += 10
            threats_detected.append({
                'type': 'page_abuse',
                'path': request.path,
                'count': behavior_data['page_views'][request.path]
            })
        
        # Check session activity patterns
        if behavior_data['last_activity']:
            time_since_last = current_time - behavior_data['last_activity']
            if time_since_last < 0.1:  # Less than 100ms between requests
                score += 20
                threats_detected.append({
                    'type': 'automated_behavior',
                    'time_between_requests': time_since_last
                })
        
        behavior_data['last_activity'] = current_time
        
        # Store updated behavior data
        cache.set(cache_key, behavior_data, 7200)  # 2 hours
        
        return score
    
    def _get_client_identifier(self, request):
        """Get privacy-preserving client identifier"""
        # For authenticated users, use user ID
        if hasattr(request, 'user') and request.user.is_authenticated:
            return f"user:{request.user.id}"
        
        # For anonymous users, use session key if available
        if hasattr(request, 'session') and request.session.session_key:
            return f"session:{request.session.session_key}"
        
        # Fallback to user agent hash (less reliable but privacy-preserving)
        user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
        ua_hash = hashlib.sha256(user_agent.encode()).hexdigest()[:16]
        return f"ua:{ua_hash}"
    
    def _calculate_alert_level(self, threat_score):
        """Calculate alert level based on threat score"""
        if threat_score >= 50:
            return self.alert_levels['CRITICAL']
        elif threat_score >= 25:
            return self.alert_levels['HIGH']
        elif threat_score >= 10:
            return self.alert_levels['MEDIUM']
        else:
            return self.alert_levels['LOW']
    
    def _log_threat_analysis(self, request, client_id, threat_score, threats_detected, alert_level):
        """Log threat analysis results"""
        if threat_score > 0:
            log_data = {
                'client_id': client_id[:16],  # Truncated for privacy
                'threat_score': threat_score,
                'alert_level': alert_level,
                'threats_count': len(threats_detected),
                'path': request.path,
                'method': request.method,
                'user_authenticated': hasattr(request, 'user') and request.user.is_authenticated,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.warning(f"IDS Alert [Level {alert_level}]: {json.dumps(log_data)}")
    
    def _handle_high_severity_threat(self, request, client_id, threats_detected, threat_score):
        """Handle high-severity threats with immediate response"""
        # Create security alert
        alert_data = {
            'client_id': client_id[:16],
            'threat_score': threat_score,
            'threats': threats_detected,
            'path': request.path,
            'method': request.method,
            'timestamp': datetime.now().isoformat(),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:200]
        }
        
        # Log critical security event
        logger.critical(f"CRITICAL SECURITY THREAT DETECTED: {json.dumps(alert_data)}")
        
        # Store alert for admin review
        cache_key = f"security_alert:{int(time.time())}"
        encrypted_alert = SECRET_MANAGER.encrypt_sensitive_data(json.dumps(alert_data))
        cache.set(cache_key, encrypted_alert, 86400)  # Store for 24 hours
        
        # Increment global threat counter
        global_threats_key = "global_threat_count"
        current_count = cache.get(global_threats_key, 0)
        cache.set(global_threats_key, current_count + 1, 3600)
        
        # If too many threats system-wide, consider system-wide protection measures
        if current_count > 100:  # More than 100 high-severity threats per hour
            logger.critical("SYSTEM UNDER ATTACK - Consider activating emergency protocols")
            self._send_emergency_alert(alert_data, current_count)
    
    def _send_emergency_alert(self, alert_data, threat_count):
        """Send emergency alert to administrators"""
        try:
            admin_email = getattr(settings, 'ADMIN_EMAIL', None)
            if admin_email:
                subject = f"CRITICAL: Enterprise Marketplace Under Attack - {threat_count} threats/hour"
                message = f"""
CRITICAL SECURITY ALERT

The Enterprise Marketplace is currently under attack with {threat_count} high-severity threats detected in the last hour.

Latest Threat Details:
- Threat Score: {alert_data['threat_score']}
- Path: {alert_data['path']}
- Method: {alert_data['method']}
- Timestamp: {alert_data['timestamp']}
- Threats: {len(alert_data['threats'])} different attack patterns

Immediate action may be required to protect the system.

This is an automated alert from the Intrusion Detection System.
                """
                
                send_mail(
                    subject,
                    message,
                    'security@enterprise.local',
                    [admin_email],
                    fail_silently=True
                )
        except Exception as e:
            logger.error(f"Failed to send emergency alert: {e}")
    
    def get_security_dashboard_data(self):
        """Get security dashboard data for monitoring"""
        current_time = time.time()
        
        # Get recent alerts
        alert_keys = cache.keys("security_alert:*")
        recent_alerts = []
        
        for key in sorted(alert_keys, reverse=True)[:20]:  # Last 20 alerts
            encrypted_alert = cache.get(key)
            if encrypted_alert:
                try:
                    alert_data = json.loads(SECRET_MANAGER.decrypt_sensitive_data(encrypted_alert))
                    recent_alerts.append(alert_data)
                except:
                    pass
        
        # Get global threat statistics
        global_threat_count = cache.get("global_threat_count", 0)
        
        return {
            'recent_alerts': recent_alerts,
            'global_threat_count': global_threat_count,
            'system_status': 'UNDER_ATTACK' if global_threat_count > 100 else 'NORMAL',
            'last_updated': datetime.now().isoformat()
        }


class IDSMiddleware:
    """Middleware to integrate IDS with Django request processing"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.ids = IntrusionDetectionSystem()
    
    def __call__(self, request):
        # Skip IDS for static files and certain paths
        skip_paths = ['/static/', '/media/', '/favicon.ico', '/robots.txt']
        if any(request.path.startswith(path) for path in skip_paths):
            return self.get_response(request)
        
        # Analyze request
        analysis_result = self.ids.analyze_request(request)
        
        # Block critical threats
        if analysis_result['blocked']:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("Access denied due to security policy.")
        
        # Add analysis results to request for further processing
        request.ids_analysis = analysis_result
        
        response = self.get_response(request)
        
        # Add security headers based on threat level
        if analysis_result['alert_level'] >= 2:
            response['X-Security-Alert-Level'] = str(analysis_result['alert_level'])
        
        return response


# Singleton instance
IDS = IntrusionDetectionSystem()