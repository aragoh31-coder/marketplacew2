#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')
django.setup()

from accounts.models import User
from accounts.pgp_service import PGPService
import gnupg

print("=== Testing Complete PGP 2FA Login Flow ===")

print("\n1. Generating test keypair...")
gpg = gnupg.GPG()
input_data = gpg.gen_key_input(
    name_email='testpgp@marketplace.local',
    passphrase='testpass123'
)
key = gpg.gen_key(input_data)

if not key:
    print("✗ Failed to generate test key")
    exit(1)

print(f"✓ Key generated: {key.fingerprint}")

public_key = gpg.export_keys(key.fingerprint)
print(f"✓ Public key exported ({len(public_key)} bytes)")

print("\n2. Creating test user...")
try:
    test_user = User.objects.get(username='pgptest')
    print("✓ Using existing test user")
except User.DoesNotExist:
    test_user = User.objects.create_user(
        username='pgptest',
        email='pgptest@marketplace.local',
        password='testpass123'
    )
    print("✓ Created new test user")

test_user.pgp_public_key = public_key
test_user.pgp_fingerprint = key.fingerprint
test_user.pgp_login_enabled = True
test_user.save()
print("✓ PGP settings configured for user")

print("\n3. Testing PGP service...")
pgp_service = PGPService()

import_result = pgp_service.import_public_key(public_key)
if not import_result['success']:
    print(f"✗ Key import failed: {import_result['error']}")
    exit(1)
print("✓ Key imported successfully")

challenge = test_user.generate_pgp_challenge()
print(f"✓ Challenge generated: {challenge[:20]}...")

challenge_message = f"""PGP Authentication Challenge for {test_user.username}
Generated at: {test_user.pgp_challenge_expires}
Challenge Code: {challenge}

Please sign this entire message with your PGP key."""

encrypt_result = pgp_service.encrypt_message(challenge_message, key.fingerprint)
if not encrypt_result['success']:
    print(f"✗ Encryption failed: {encrypt_result['error']}")
    exit(1)

encrypted_message = encrypt_result['encrypted_message']
print("✓ Challenge encrypted successfully")
print(f"✓ Encrypted message format: {encrypted_message[:50]}...")

if encrypted_message.startswith('-----BEGIN PGP MESSAGE-----'):
    print("✓ Valid PGP message format confirmed")
else:
    print("✗ Invalid PGP message format!")
    exit(1)

print("\n4. Simulating user decryption and signing...")
decrypted = gpg.decrypt(encrypted_message, passphrase='testpass123')
if not decrypted.ok:
    print(f"✗ Decryption failed: {decrypted.stderr}")
    exit(1)

decrypted_text = str(decrypted)
print("✓ Message decrypted successfully")

signed = gpg.sign(decrypted_text, passphrase='testpass123', clearsign=True)
if not signed:
    print("✗ Signing failed")
    exit(1)

signed_message = str(signed)
print("✓ Message signed successfully")

print("\n5. Testing signature verification...")
verify_result = pgp_service.extract_message_from_signature(signed_message)
if not verify_result['success']:
    print(f"✗ Signature verification failed: {verify_result['error']}")
    exit(1)

extracted_message = verify_result['message']
print("✓ Signature verified and message extracted")

if challenge in extracted_message:
    print("✓ Challenge code found in extracted message")
    
    if test_user.verify_pgp_challenge(challenge):
        print("✓ Challenge verification successful")
    else:
        print("✗ Challenge verification failed")
        exit(1)
else:
    print("✗ Challenge code not found in extracted message")
    exit(1)

print("\n=== PGP 2FA Login Flow Test Complete ===")
print("✅ All tests passed! PGP 2FA is working correctly.")
