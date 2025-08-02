"""
Admin Panel Configuration
This file contains sensitive admin panel settings.
Keep this file secure and do not commit to version control.
"""

ADMIN_SECONDARY_PASSWORD = "SecureAdmin2024!"

ALLOWED_ADMIN_PGP_FINGERPRINTS = [
]

ADMIN_PANEL_CONFIG = {
    'SECONDARY_PASSWORD': ADMIN_SECONDARY_PASSWORD,
    'REQUIRE_PGP_AFTER_AUTH': False,  # Set to True to require PGP verification
    'MAX_FAILED_ATTEMPTS': 3,
    'LOCKOUT_DURATION': 3600,  # 1 hour in seconds
    'SESSION_TIMEOUT': 7200,   # 2 hours in seconds
}

ADMIN_PGP_CONFIG = {
    'ENFORCE_PGP': False,  # Set to True to enforce PGP verification
    'CHALLENGE_TIMEOUT': 300,  # 5 minutes in seconds
    'ADMIN_PUBLIC_KEY': '',  # Admin's PGP public key for verification
}
