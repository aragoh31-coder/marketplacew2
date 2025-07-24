#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'marketplace.settings')
django.setup()

import gnupg
import tempfile
import shutil

temp_dir = tempfile.mkdtemp()
gpg = gnupg.GPG(gnupghome=temp_dir)

print("Generating test PGP key...")

input_data = gpg.gen_key_input(
    name_email='testuser@marketplace.local',
    passphrase='testpass123',
    key_length=2048
)
key = gpg.gen_key(input_data)

if key:
    public_key = gpg.export_keys(key.fingerprint)
    print('=== TEST PGP PUBLIC KEY ===')
    print(public_key)
    print('=== END KEY ===')
    print(f'Fingerprint: {key.fingerprint}')
    
    with open('/home/ubuntu/test_public_key.asc', 'w') as f:
        f.write(public_key)
    print('Key saved to /home/ubuntu/test_public_key.asc')
else:
    print('Failed to generate key')

shutil.rmtree(temp_dir)
