import json
import logging
import threading
import time

from django.conf import settings
from django.core.cache import cache
from core.utils.security import get_session_hash

logger = logging.getLogger("performance")


class SecurityPerformanceMonitor:
    """Real-time monitoring of security performance"""

    def __init__(self):
        self.metrics = {
            "requests_total": 0,
            "requests_blocked": 0,
            "requests_allowed": 0,
            "avg_response_time": 0,
            "active_ips": set(),
            "blocked_ips": set(),
            "attack_vectors": {},
        }
        self.monitoring = False
        self.thread = None

    def start_monitoring(self):
        """Start background monitoring"""
        if not self.monitoring:
            self.monitoring = True
            self.thread = threading.Thread(target=self._monitor_loop)
            self.thread.daemon = True
            self.thread.start()
            logger.info("Security performance monitoring started")

    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
        if self.thread:
            self.thread.join()
        logger.info("Security performance monitoring stopped")

    def record_request(self, request, blocked=False, response_time=None):
        """Record security metrics for a request"""
        client_id = get_session_hash(request)

        self.metrics["requests_total"] += 1
        if blocked:
            self.metrics["requests_blocked"] += 1
            self.metrics["blocked_ips"].add(client_id)
        else:
            self.metrics["requests_allowed"] += 1
            self.metrics["active_ips"].add(client_id)

        if response_time:
            current_avg = self.metrics["avg_response_time"]
            total_requests = self.metrics["requests_total"]
            self.metrics["avg_response_time"] = (
                current_avg * (total_requests - 1) + response_time
            ) / total_requests

        self._detect_attack_vector(request, blocked)

    def _monitor_loop(self):
        """Background monitoring loop"""
        while self.monitoring:
            try:
                self._collect_system_metrics()
                self._check_alert_thresholds()
                self._save_metrics_snapshot()
                time.sleep(
                    getattr(settings, "SECURITY_MONITORING", {}).get(
                        "METRICS_INTERVAL", 30
                    )
                )
            except Exception as e:
                logger.error(f"Monitoring error: {e}")

    def _collect_system_metrics(self):
        """Collect system-level metrics"""
        try:
            import psutil

            cpu_percent = psutil.cpu_percent()
            memory = psutil.virtual_memory()

            connections = len(psutil.net_connections(kind="inet"))

            cache_stats = self._get_cache_stats()

            system_metrics = {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "active_connections": connections,
                "cache_hit_rate": cache_stats.get("hit_rate", 0),
                "timestamp": time.time(),
            }

            cache.set("security_system_metrics", system_metrics, 60)
        except ImportError:
            pass

    def _get_cache_stats(self):
        """Get cache performance statistics"""
        try:
            from django_redis import get_redis_connection

            redis_conn = get_redis_connection("default")
            info = redis_conn.info()

            hits = int(info.get("keyspace_hits", 0))
            misses = int(info.get("keyspace_misses", 0))
            total = hits + misses

            hit_rate = (hits / total * 100) if total > 0 else 0

            return {
                "hit_rate": hit_rate,
                "hits": hits,
                "misses": misses,
                "memory_usage": info.get("used_memory_human", "N/A"),
            }
        except Exception:
            return {}

    def _check_alert_thresholds(self):
        """Check if metrics exceed alert thresholds"""
        thresholds = getattr(settings, "SECURITY_MONITORING", {}).get(
            "ALERT_THRESHOLDS", {}
        )

        total_requests = self.metrics["requests_total"]
        if total_requests > 0:
            rps = total_requests / 60  # Approximate RPS over last minute
            block_rate = (self.metrics["requests_blocked"] / total_requests) * 100

            if rps > thresholds.get("requests_per_second", 50):
                logger.warning(f"High request rate: {rps:.1f} RPS")

            if block_rate > thresholds.get("block_rate_percent", 70):
                logger.warning(f"High block rate: {block_rate:.1f}%")

            if self.metrics["avg_response_time"] > thresholds.get(
                "response_time_ms", 500
            ):
                logger.warning(
                    f"High response time: {self.metrics['avg_response_time']:.1f}ms"
                )

    def _save_metrics_snapshot(self):
        """Save current metrics snapshot"""
        snapshot = {
            "timestamp": time.time(),
            "requests_per_minute": self.metrics["requests_total"],
            "block_rate_percent": (
                self.metrics["requests_blocked"]
                / max(1, self.metrics["requests_total"])
            )
            * 100,
            "unique_ips": len(self.metrics["active_ips"]),
            "blocked_ips": len(self.metrics["blocked_ips"]),
            "avg_response_time": self.metrics["avg_response_time"],
            "attack_vectors": dict(self.metrics["attack_vectors"]),
        }

        cache.set("security_metrics_snapshot", snapshot, 300)

        self.metrics = {
            "requests_total": 0,
            "requests_blocked": 0,
            "requests_allowed": 0,
            "avg_response_time": 0,
            "active_ips": set(),
            "blocked_ips": set(),
            "attack_vectors": {},
        }

    def _detect_attack_vector(self, request, blocked):
        """Detect and categorize attack vectors"""
        if not blocked:
            return

        vector = "unknown"
        path = request.path.lower()
        user_agent = request.META.get("HTTP_USER_AGENT", "").lower()

        if any(sql in path for sql in ["union", "select", "drop"]):
            vector = "sql_injection"
        elif "<script" in path or "javascript:" in path:
            vector = "xss"
        elif any(bot in user_agent for bot in ["python", "curl", "bot"]):
            vector = "automated_bot"
        elif len(path) > 1000:
            vector = "path_overflow"
        else:
            vector = "rate_limit"

        self.metrics["attack_vectors"][vector] = (
            self.metrics["attack_vectors"].get(vector, 0) + 1
        )


    def get_current_metrics(self):
        """Get current performance metrics"""
        snapshot = cache.get("security_metrics_snapshot", {})
        system_metrics = cache.get("security_system_metrics", {})

        return {
            "security": snapshot,
            "system": system_metrics,
            "cache_stats": self._get_cache_stats(),
        }


security_monitor = SecurityPerformanceMonitor()
