from django.core.management.base import BaseCommand
from accounts.pgp_service import PGPService
import gnupg

class Command(BaseCommand):
    help = 'Test PGP compatibility with various key types'

    def handle(self, *args, **options):
        self.stdout.write("🔐 Testing PGP Compatibility...\n")
        
        pgp_service = PGPService()
        self.stdout.write("✅ PGP Service initialized")
        
        test_keys = self.generate_test_keys()
        
        for key_type, key_data in test_keys.items():
            self.test_key_type(pgp_service, key_type, key_data)
        
        self.stdout.write(self.style.SUCCESS("\n✅ All PGP tests completed!"))
    
    def generate_test_keys(self):
        """Generate various types of test keys"""
        gpg = gnupg.GPG()
        test_keys = {}
        
        self.stdout.write("\n📝 Generating test keys...")
        
        self.stdout.write("  Generating RSA 2048...")
        key_input = gpg.gen_key_input(
            name_email='rsa2048@test.com',
            key_type='RSA',
            key_length=2048,
            key_usage='encrypt,sign',
            passphrase='test123'
        )
        key = gpg.gen_key(key_input)
        if key:
            test_keys['RSA-2048'] = {
                'fingerprint': key.fingerprint,
                'public_key': gpg.export_keys(key.fingerprint),
                'passphrase': 'test123'
            }
        
        self.stdout.write("  Generating RSA 4096...")
        key_input = gpg.gen_key_input(
            name_email='rsa4096@test.com',
            key_type='RSA',
            key_length=4096,
            passphrase='test123'
        )
        key = gpg.gen_key(key_input)
        if key:
            test_keys['RSA-4096'] = {
                'fingerprint': key.fingerprint,
                'public_key': gpg.export_keys(key.fingerprint),
                'passphrase': 'test123'
            }
        
        self.stdout.write("  Generating DSA/ElGamal...")
        key_input = gpg.gen_key_input(
            name_email='dsa@test.com',
            key_type='DSA',
            key_length=2048,
            subkey_type='ELG-E',
            subkey_length=2048,
            passphrase='test123'
        )
        key = gpg.gen_key(key_input)
        if key:
            test_keys['DSA-ElGamal'] = {
                'fingerprint': key.fingerprint,
                'public_key': gpg.export_keys(key.fingerprint),
                'passphrase': 'test123'
            }
        
        return test_keys
    
    def test_key_type(self, pgp_service, key_type, key_data):
        """Test a specific key type"""
        self.stdout.write(f"\n🧪 Testing {key_type}...")
        
        import_result = pgp_service.import_public_key(key_data['public_key'])
        
        if not import_result['success']:
            self.stdout.write(self.style.ERROR(f"  ❌ Import failed: {import_result['error']}"))
            return
        
        self.stdout.write(f"  ✅ Import successful")
        self.stdout.write(f"     Fingerprint: {import_result['fingerprint'][:16]}...")
        self.stdout.write(f"     Algorithm: {import_result.get('algorithm', 'Unknown')}")
        self.stdout.write(f"     Key Length: {import_result.get('length', 'Unknown')}")
        
        test_message = f"Test message for {key_type} encryption"
        encrypt_result = pgp_service.encrypt_message(
            test_message,
            import_result['fingerprint']
        )
        
        if not encrypt_result['success']:
            self.stdout.write(self.style.ERROR(f"  ❌ Encryption failed: {encrypt_result['error']}"))
            return
        
        self.stdout.write(f"  ✅ Encryption successful")
        
        key_info = pgp_service.get_key_info(import_result['fingerprint'])
        if key_info and key_info.get('success'):
            caps = key_info.get('capabilities', {})
            self.stdout.write(f"     Algorithm: {key_info.get('algorithm', 'Unknown')}")
            self.stdout.write(f"     Key Length: {key_info.get('length', 'Unknown')} bits")
            self.stdout.write(f"     Can Encrypt: {caps.get('can_encrypt', False)}")
            self.stdout.write(f"     Can Sign: {caps.get('can_sign', False)}")
            self.stdout.write(f"     Has Subkey: {caps.get('has_encryption_subkey', False)}")
            self.stdout.write(f"     Created: {key_info.get('created', 'Unknown')}")
            self.stdout.write(f"     Expires: {key_info.get('expires', 'Never')}")
        else:
            self.stdout.write("     ⚠️ Could not get detailed key info")
