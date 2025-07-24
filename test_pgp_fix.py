#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')
django.setup()

from accounts.pgp_service import PGPService
import gnupg

print("Testing GPG installation...")
gpg = gnupg.GPG()
print(f"GPG Version: {gpg.version}")
print(f"GPG Binary: {gpg.gpgbinary}")

print("\nGenerating test keypair...")
input_data = gpg.gen_key_input(
    name_email='test@marketplace.local',
    passphrase='testpass123'
)
key = gpg.gen_key(input_data)

if key:
    print(f"✓ Key generated: {key.fingerprint}")
    
    public_key = gpg.export_keys(key.fingerprint)
    print(f"✓ Public key length: {len(public_key)} bytes")
    
    print("\nTesting PGPService...")
    pgp_service = PGPService()
    
    import_result = pgp_service.import_public_key(public_key)
    print(f"Import result: {import_result}")
    
    if import_result['success']:
        test_message = "Test message for encryption"
        encrypt_result = pgp_service.encrypt_message(test_message, key.fingerprint)
        print(f"Encryption result: Success={encrypt_result['success']}")
        
        if encrypt_result['success']:
            print("\n✓ Encrypted message:")
            print(encrypt_result['encrypted_message'][:200] + "...")
            
            if encrypt_result['encrypted_message'].startswith('-----BEGIN PGP MESSAGE-----'):
                print("✓ Valid PGP message format")
            else:
                print("✗ Invalid PGP message format!")
else:
    print("✗ Failed to generate test key")

print("\nPGP system test complete!")
