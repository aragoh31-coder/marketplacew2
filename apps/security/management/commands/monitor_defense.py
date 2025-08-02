from django.core.management.base import BaseCommand
from django.core.cache import cache
import time
import json

class Command(BaseCommand):
    help = 'Monitor advanced security defense effectiveness'
    
    def add_arguments(self, parser):
        parser.add_argument('--duration', type=int, default=300, help='Monitor duration in seconds')
        parser.add_argument('--interval', type=int, default=30, help='Report interval in seconds')
    
    def handle(self, *args, **options):
        duration = options['duration']
        interval = options['interval']
        
        self.stdout.write("Starting advanced security monitoring...")
        
        start_time = time.time()
        while time.time() - start_time < duration:
            stats = self.get_comprehensive_stats()
            self.display_stats(stats)
            time.sleep(interval)
    
    def get_comprehensive_stats(self):
        circuit_stats = cache.get('circuit_defense_stats', {})
        resource_stats = cache.get('system_load_metrics', {})
        security_stats = cache.get('security_metrics_snapshot', {})
        
        return {
            'timestamp': time.time(),
            'circuit_defense': circuit_stats,
            'resource_protection': resource_stats,
            'security_metrics': security_stats,
            'threat_level': self.calculate_overall_threat_level(circuit_stats, resource_stats, security_stats)
        }
    
    def calculate_overall_threat_level(self, circuit_stats, resource_stats, security_stats):
        threat_score = 0
        
        if circuit_stats.get('active_circuits', 0) > 50:
            threat_score += 25
        
        if resource_stats.get('level') == 'critical':
            threat_score += 30
        elif resource_stats.get('level') == 'high':
            threat_score += 20
        
        block_rate = security_stats.get('block_rate_percent', 0)
        if block_rate > 70:
            threat_score += 25
        elif block_rate > 50:
            threat_score += 15
        
        rps = security_stats.get('requests_per_minute', 0) / 60
        if rps > 50:
            threat_score += 20
        elif rps > 20:
            threat_score += 10
        
        if threat_score >= 70:
            return 'CRITICAL'
        elif threat_score >= 50:
            return 'HIGH'
        elif threat_score >= 30:
            return 'ELEVATED'
        else:
            return 'NORMAL'
    
    def display_stats(self, stats):
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"ADVANCED SECURITY MONITOR - {time.strftime('%H:%M:%S')}")
        self.stdout.write(f"{'='*60}")
        
        threat_level = stats['threat_level']
        color = self.style.ERROR if threat_level == 'CRITICAL' else \
                self.style.WARNING if threat_level in ['HIGH', 'ELEVATED'] else \
                self.style.SUCCESS
        
        self.stdout.write(f"THREAT LEVEL: {color(threat_level)}")
        
        resource_stats = stats.get('resource_protection', {})
        self.stdout.write(f"CPU: {resource_stats.get('cpu_percent', 0):.1f}% | "
                         f"Memory: {resource_stats.get('memory_percent', 0):.1f}% | "
                         f"Connections: {resource_stats.get('connections', 0)}")
        
        security_stats = stats.get('security_metrics', {})
        self.stdout.write(f"Requests/min: {security_stats.get('requests_per_minute', 0)} | "
                         f"Block rate: {security_stats.get('block_rate_percent', 0):.1f}% | "
                         f"Unique IPs: {security_stats.get('unique_ips', 0)}")
        
        circuit_stats = stats.get('circuit_defense', {})
        self.stdout.write(f"Active circuits: {circuit_stats.get('active_circuits', 0)} | "
                         f"Blocked circuits: {circuit_stats.get('blocked_circuits', 0)}")
