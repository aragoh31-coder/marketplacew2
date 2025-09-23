#!/usr/bin/env python3
"""
Manual Tor descriptor refresh script
Usage: python scripts/manual_tor_refresh.py
"""

import os
import sys
import django
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')
django.setup()

from vendors.tasks import refresh_tor_descriptors

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("🔄 Manually refreshing Tor descriptors...")
    result = refresh_tor_descriptors()
    logger.info(f"✅ Result: {result}")

if __name__ == '__main__':
    main()
