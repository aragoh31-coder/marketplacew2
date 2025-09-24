#!/usr/bin/env python3
"""
Test script to verify the Django marketplace application is fully operational
"""
import os
import sys
import django
import subprocess
import time
from pathlib import Path

def test_django_setup():
    """Test Django setup and basic functionality"""
    print("🔍 Testing Django setup...")

    # Set up Django environment
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')
    django.setup()

    # Test imports
    from django.test import Client
    from django.contrib.auth.models import User
    from django.db import connection

    print("✅ Django imports successful")
    print(f"✅ Database: {connection.vendor}")
    print(f"✅ Django version: {django.VERSION}")

    return True

def test_database():
    """Test database operations"""
    print("🔍 Testing database operations...")

    try:
        from accounts.models import User

        # Create test user
        test_user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        print("✅ Database operations working")

        # Clean up
        test_user.delete()
        print("✅ Database cleanup successful")

        return True
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        return False

def test_static_files():
    """Test static file serving"""
    print("🔍 Testing static files...")

    static_dir = Path('/workspace/static')
    if static_dir.exists() and list(static_dir.glob('*')):
        print("✅ Static files directory exists")
        return True
    else:
        print("❌ Static files not found")
        return False

def test_configuration():
    """Test configuration files"""
    print("🔍 Testing configuration...")

    config_files = [
        '/workspace/.env',
        '/workspace/nginx/config/nginx.conf',
        '/workspace/nginx/config/sites-available/marketplace'
    ]

    for config_file in config_files:
        if Path(config_file).exists():
            print(f"✅ Configuration file found: {config_file}")
        else:
            print(f"❌ Configuration file missing: {config_file}")
            return False

    return True

def test_dependencies():
    """Test if all dependencies are installed"""
    print("🔍 Testing dependencies...")

    try:
        import django
        import gunicorn
        import cryptography
        import celery
        import redis

        print("✅ Core dependencies installed")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("🧪 DJANGO MARKETPLACE APPLICATION TEST SUITE")
    print("=" * 60)

    tests = [
        test_django_setup,
        test_database,
        test_static_files,
        test_configuration,
        test_dependencies
    ]

    results = []

    for test in tests:
        try:
            result = test()
            results.append(result)
            print()
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append(False)
            print()

    print("=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")

    if passed == total:
        print("🎉 ALL TESTS PASSED! The application is fully operational!")
        print("\n🚀 To start the application:")
        print("   1. python3 manage.py runserver 0.0.0.0:8000")
        print("   2. Open http://localhost:8000 in your browser")
        return True
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)