import logging
import re
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("marketplace.security")


class SecurityEventClassifier:
    """Classify and analyze security events"""

    EVENT_PATTERNS = {
        "brute_force": {
            "patterns": [
                r"multiple.*failed.*login",
                r"repeated.*authentication.*failure",
                r"excessive.*login.*attempts",
            ],
            "risk_level": "high",
            "auto_action": "rate_limit",
        },
        "suspicious_activity": {
            "patterns": [
                r"unusual.*access.*pattern",
                r"suspicious.*user.*agent",
                r"automated.*behavior.*detected",
            ],
            "risk_level": "medium",
            "auto_action": "monitor",
        },
        "account_takeover": {
            "patterns": [
                r"session.*hijack",
                r"unauthorized.*access",
                r"account.*compromise",
            ],
            "risk_level": "critical",
            "auto_action": "block_user",
        },
        "data_breach_attempt": {
            "patterns": [
                r"sql.*injection",
                r"xss.*attempt",
                r"unauthorized.*data.*access",
            ],
            "risk_level": "critical",
            "auto_action": "block_ip",
        },
        "financial_fraud": {
            "patterns": [
                r"fraudulent.*transaction",
                r"suspicious.*payment",
                r"money.*laundering",
            ],
            "risk_level": "critical",
            "auto_action": "freeze_account",
        },
    }

    @classmethod
    def classify_event(cls, event_description, context=None):
        """Classify security event and determine risk level"""
        try:
            event_lower = event_description.lower()

            for event_type, config in cls.EVENT_PATTERNS.items():
                for pattern in config["patterns"]:
                    if re.search(pattern, event_lower):
                        return {
                            "event_type": event_type,
                            "risk_level": config["risk_level"],
                            "auto_action": config["auto_action"],
                            "confidence": cls._calculate_confidence(
                                pattern, event_lower
                            ),
                            "classified_at": timezone.now().isoformat(),
                        }

            return {
                "event_type": "unknown",
                "risk_level": "low",
                "auto_action": "log_only",
                "confidence": 0.5,
                "classified_at": timezone.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to classify security event: {e}")
            return {
                "event_type": "classification_error",
                "risk_level": "medium",
                "auto_action": "log_only",
                "error": str(e),
            }

    @classmethod
    def _calculate_confidence(cls, pattern, text):
        """Calculate confidence score for pattern match"""
        try:
            matches = len(re.findall(pattern, text))
            text_length = len(text.split())

            confidence = min(1.0, (matches * 10) / max(text_length, 1))
            return round(confidence, 2)

        except Exception:
            return 0.5

    @classmethod
    def analyze_event_trends(cls, user_id=None, time_window_hours=24):
        """Analyze security event trends"""
        try:
            cache_key = f"security_trends:{user_id or 'global'}:{time_window_hours}"
            cached_analysis = cache.get(cache_key)

            if cached_analysis:
                return cached_analysis

            from apps.security.models import SecurityEvent

            cutoff_time = timezone.now() - timedelta(hours=time_window_hours)

            events_query = SecurityEvent.objects.filter(created_at__gte=cutoff_time)
            if user_id:
                events_query = events_query.filter(user_id=user_id)

            events = events_query.values("event_type", "risk_level").distinct()

            analysis = {
                "time_window_hours": time_window_hours,
                "total_events": events_query.count(),
                "event_types": {},
                "risk_distribution": {"low": 0, "medium": 0, "high": 0, "critical": 0},
                "trends": [],
                "analyzed_at": timezone.now().isoformat(),
            }

            for event in events:
                event_type = event["event_type"]
                risk_level = event["risk_level"]

                if event_type not in analysis["event_types"]:
                    analysis["event_types"][event_type] = 0

                analysis["event_types"][event_type] += 1
                analysis["risk_distribution"][risk_level] += 1

            analysis["trends"] = cls._identify_trends(analysis)

            cache.set(cache_key, analysis, 1800)  # Cache for 30 minutes

            return analysis

        except Exception as e:
            logger.error(f"Failed to analyze event trends: {e}")
            return {"error": str(e), "analyzed_at": timezone.now().isoformat()}

    @classmethod
    def _identify_trends(cls, analysis):
        """Identify security trends from analysis"""
        trends = []

        try:
            total_events = analysis["total_events"]

            if total_events == 0:
                return trends

            if total_events > 100:
                trends.append(
                    {
                        "type": "high_activity",
                        "severity": "medium",
                        "description": f"High security event volume: {total_events} events",
                    }
                )

            critical_events = analysis["risk_distribution"]["critical"]
            if critical_events > 0:
                trends.append(
                    {
                        "type": "critical_events",
                        "severity": "critical",
                        "description": f"{critical_events} critical security events detected",
                    }
                )

            brute_force_events = analysis["event_types"].get("brute_force", 0)
            if brute_force_events > 5:
                trends.append(
                    {
                        "type": "brute_force_pattern",
                        "severity": "high",
                        "description": f"Potential brute force attack: {brute_force_events} attempts",
                    }
                )

            return trends

        except Exception as e:
            logger.error(f"Failed to identify trends: {e}")
            return []


class ThreatDetector:
    """Advanced threat detection system"""

    @classmethod
    def detect_threats(cls, request, user=None):
        """Detect potential threats from request"""
        threats = []

        try:
            user_agent = request.META.get("HTTP_USER_AGENT", "")
            if cls._is_suspicious_user_agent(user_agent):
                threats.append(
                    {
                        "type": "suspicious_user_agent",
                        "severity": "medium",
                        "details": {"user_agent": user_agent[:100]},
                    }
                )

            if cls._detect_rapid_requests(request):
                threats.append(
                    {
                        "type": "rapid_requests",
                        "severity": "high",
                        "details": {"rate_limit_exceeded": True},
                    }
                )

            if cls._detect_injection_attempts(request):
                threats.append(
                    {
                        "type": "injection_attempt",
                        "severity": "critical",
                        "details": {"path": request.path},
                    }
                )

            return threats

        except Exception as e:
            logger.error(f"Failed to detect threats: {e}")
            return []

    @classmethod
    def _is_suspicious_user_agent(cls, user_agent):
        """Check if user agent is suspicious"""
        suspicious_patterns = [
            r"bot",
            r"crawler",
            r"spider",
            r"scraper",
            r"curl",
            r"wget",
            r"python-requests",
        ]

        user_agent_lower = user_agent.lower()

        for pattern in suspicious_patterns:
            if re.search(pattern, user_agent_lower):
                return True

        return False

    @classmethod
    def _detect_rapid_requests(cls, request):
        """Detect rapid request patterns"""
        try:
            client_id = cls._get_client_identifier(request)
            cache_key = f"request_rate:{client_id}"

            current_requests = cache.get(cache_key, 0)

            if current_requests > 60:  # More than 60 requests per minute
                return True

            cache.set(cache_key, current_requests + 1, 60)
            return False

        except Exception:
            return False

    @classmethod
    def _detect_injection_attempts(cls, request):
        """Detect SQL injection and XSS attempts"""
        injection_patterns = [
            r"union.*select",
            r"drop.*table",
            r"<script",
            r"javascript:",
            r"eval\(",
            r"exec\(",
        ]

        path_lower = request.path.lower()
        for pattern in injection_patterns:
            if re.search(pattern, path_lower):
                return True

        for key, value in request.GET.items():
            value_lower = str(value).lower()
            for pattern in injection_patterns:
                if re.search(pattern, value_lower):
                    return True

        return False

    @classmethod
    def _get_client_identifier(cls, request):
        """Get client identifier for rate limiting"""
        import hashlib

        user_agent = request.META.get("HTTP_USER_AGENT", "")
        accept_lang = request.META.get("HTTP_ACCEPT_LANGUAGE", "")

        identifier_data = f"{user_agent}:{accept_lang}"
        return hashlib.sha256(identifier_data.encode()).hexdigest()[:16]
