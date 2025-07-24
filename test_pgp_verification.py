#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')
django.setup()

from accounts.pgp_service import PGPService
import gnupg

print("🧪 Testing PGP Verification Flow...")

gpg = gnupg.GPG()
input_data = gpg.gen_key_input(
    name_email='test@example.com',
    passphrase='test'
)
key = gpg.gen_key(input_data)

if key:
    print(f"\n✓ Test key generated: {key.fingerprint}")
    
    public_key = gpg.export_keys(key.fingerprint)
    
    pgp_service = PGPService()
    
    import_result = pgp_service.import_public_key(public_key)
    print(f"✓ Key imported successfully")
    
    verification_code = "TestVerificationCode123"
    message = f"PGP Key Verification\n\nVerification Code: {verification_code}\n"
    
    encrypt_result = pgp_service.encrypt_message(message, key.fingerprint)
    
    if encrypt_result['success']:
        print("\n✓ Verification message encrypted")
        print("Encrypted message preview:")
        print(encrypt_result['encrypted_message'][:200] + "...")
        
        decrypted = gpg.decrypt(encrypt_result['encrypted_message'], passphrase='test')
        
        if decrypted.ok:
            print(f"\n✓ Successfully decrypted: {str(decrypted)}")
            print("\n✅ Verification flow working correctly!")
        else:
            print(f"\n✗ Decryption failed: {decrypted.status}")
    else:
        print(f"\n✗ Encryption failed: {encrypt_result['error']}")
