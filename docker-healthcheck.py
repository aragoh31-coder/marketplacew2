#!/usr/bin/env python3
import os
import sys
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')
django.setup()

def check_database():
    """Check database connectivity"""
    try:
        from django.db import connection
        cursor = connection.cursor()
        cursor.execute("SELECT 1")
        return True
    except Exception as e:
        print(f"Database check failed: {e}")
        return False

def check_redis():
    """Check Redis connectivity"""
    try:
        import redis
        r = redis.Redis.from_url(settings.REDIS_URL)
        r.ping()
        return True
    except Exception as e:
        print(f"Redis check failed: {e}")
        return False

def main():
    """Run health checks"""
    checks = [
        ("Database", check_database),
        ("Redis", check_redis),
    ]
    
    all_passed = True
    for name, check_func in checks:
        try:
            if check_func():
                print(f"✅ {name}: OK")
            else:
                print(f"❌ {name}: FAILED")
                all_passed = False
        except Exception as e:
            print(f"❌ {name}: ERROR - {e}")
            all_passed = False
    
    if all_passed:
        print("🎉 All health checks passed!")
        sys.exit(0)
    else:
        print("💥 Some health checks failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
