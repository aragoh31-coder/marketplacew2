#!/usr/bin/env python3
import subprocess
import time
import json
import re
from datetime import datetime

class DDosMonitor:
    def __init__(self):
        self.start_time = datetime.now()
        self.attack_patterns = {
            'rate_limit_exceeded': 0,
            'bot_detected': 0,
            'suspicious_paths': 0,
            'ip_blocks': 0,
            'pow_challenges': 0,
            'connection_spikes': 0
        }
        
    def check_openresty_logs(self):
        """Check OpenResty logs for attack indicators"""
        try:
            result = subprocess.run(['docker-compose', 'logs', '--tail=20', 'openresty'], 
                                  capture_output=True, text=True, cwd='/home/ubuntu/marketplace')
            logs = result.stdout
            
            self.attack_patterns['rate_limit_exceeded'] += len(re.findall(r'429|Rate limit exceeded', logs))
            self.attack_patterns['bot_detected'] += len(re.findall(r'403.*Bot detected', logs))
            self.attack_patterns['suspicious_paths'] += len(re.findall(r'Suspicious request blocked', logs))
            self.attack_patterns['ip_blocks'] += len(re.findall(r'Blocked IP:', logs))
            self.attack_patterns['pow_challenges'] += len(re.findall(r'PoW required', logs))
            
            return logs
        except Exception as e:
            return f"Error checking OpenResty logs: {e}"
    
    def check_django_logs(self):
        """Check Django logs for security events"""
        try:
            result = subprocess.run(['docker-compose', 'logs', '--tail=20', 'django'], 
                                  capture_output=True, text=True, cwd='/home/ubuntu/marketplace')
            logs = result.stdout
            
            security_events = len(re.findall(r'SECURITY|WARNING|ERROR', logs))
            return logs, security_events
        except Exception as e:
            return f"Error checking Django logs: {e}", 0
    
    def check_system_metrics(self):
        """Check system resource usage"""
        try:
            result = subprocess.run(['docker', 'stats', '--no-stream', '--format', 
                                   'table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}'], 
                                  capture_output=True, text=True)
            return result.stdout
        except Exception as e:
            return f"Error checking system metrics: {e}"
    
    def generate_report(self):
        """Generate monitoring report"""
        duration = datetime.now() - self.start_time
        
        report = f"""
=== DDOS MONITORING REPORT ===
Duration: {duration}
Start: {self.start_time}
End: {datetime.now()}

ATTACK PATTERNS DETECTED:
- Rate Limit Exceeded: {self.attack_patterns['rate_limit_exceeded']}
- Bot Detected: {self.attack_patterns['bot_detected']}
- Suspicious Paths: {self.attack_patterns['suspicious_paths']}
- IP Blocks: {self.attack_patterns['ip_blocks']}
- PoW Challenges: {self.attack_patterns['pow_challenges']}
- Connection Spikes: {self.attack_patterns['connection_spikes']}

TOTAL SECURITY EVENTS: {sum(self.attack_patterns.values())}
"""
        return report

if __name__ == "__main__":
    monitor = DDosMonitor()
    print("Starting DDoS monitoring...")
    
    for minute in range(10):
        print(f"\n=== MINUTE {minute + 1}/10 ===")
        print(f"Time: {datetime.now()}")
        
        openresty_logs = monitor.check_openresty_logs()
        django_logs, security_events = monitor.check_django_logs()
        system_stats = monitor.check_system_metrics()
        
        print("OpenResty recent activity:")
        print(openresty_logs[-500:] if len(openresty_logs) > 500 else openresty_logs)
        
        print(f"\nDjango security events: {security_events}")
        print("\nSystem stats:")
        print(system_stats)
        
        if minute < 9:  # Don't sleep on last iteration
            time.sleep(60)
    
    print(monitor.generate_report())
