#!/usr/bin/env python3
"""
Manual Tor descriptor refresh script
Usage: python scripts/manual_tor_refresh.py
"""

import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "marketplace.settings")
django.setup()

from vendors.tasks import refresh_tor_descriptors


def main():
    print("🔄 Manually refreshing Tor descriptors...")
    result = refresh_tor_descriptors()
    print(f"✅ Result: {result}")


if __name__ == "__main__":
    main()
