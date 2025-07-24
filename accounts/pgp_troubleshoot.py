import logging
from .pgp_service import PGPService

logger = logging.getLogger(__name__)

class PGPTroubleshooter:
    """Diagnostic tools for PGP issues"""
    
    def __init__(self):
        self.pgp_service = PGPService()
    
    def diagnose_key_issues(self, key_data):
        """Comprehensive key diagnosis"""
        issues = []
        warnings = []
        
        validation = self.pgp_service.validate_key_format(key_data)
        if not validation['success']:
            issues.append(f"Format validation failed: {validation['error']}")
            return {'issues': issues, 'warnings': warnings, 'can_proceed': False}
        
        import_result = self.pgp_service.import_public_key(key_data)
        if not import_result['success']:
            issues.append(f"Import failed: {import_result['error']}")
            return {'issues': issues, 'warnings': warnings, 'can_proceed': False}
        
        fingerprint = import_result['fingerprint']
        key_info = self.pgp_service.get_key_info(fingerprint)
        
        if key_info and key_info.get('success'):
            caps = key_info.get('capabilities', {})
            
            if caps.get('is_expired'):
                issues.append("Key has expired")
            
            if caps.get('is_revoked'):
                issues.append("Key has been revoked")
            
            if not caps.get('can_encrypt') and not caps.get('has_encryption_subkey'):
                issues.append("Key does not support encryption")
            
            if caps.get('can_encrypt') and not caps.get('has_encryption_subkey'):
                warnings.append("Key can encrypt but has no encryption subkey")
            
            algorithm = key_info.get('algorithm', '')
            if 'DSA' in algorithm and not caps.get('has_encryption_subkey'):
                warnings.append("DSA keys typically need ElGamal subkeys for encryption")
        
        test_result = self.pgp_service.test_key_encryption(fingerprint)
        if not test_result['success']:
            issues.append(f"Encryption test failed: {test_result['error']}")
        
        can_proceed = len(issues) == 0
        
        return {
            'issues': issues,
            'warnings': warnings,
            'can_proceed': can_proceed,
            'key_info': key_info
        }
    
    def get_compatibility_report(self):
        """Generate compatibility report"""
        report = {
            'gpg_version': str(self.pgp_service.gpg.version),
            'gpg_binary': self.pgp_service.gpg.gpgbinary,
            'temp_dir': self.pgp_service.temp_dir,
            'supported_algorithms': [
                'RSA (1024, 2048, 3072, 4096 bits)',
                'DSA (1024, 2048 bits)',
                'ElGamal (1024, 2048, 3072, 4096 bits)',
                'ECDSA (P-256, P-384, P-521)',
                'ECDH (P-256, P-384, P-521)',
                'EdDSA (Ed25519)'
            ],
            'supported_formats': [
                'ASCII Armored (.asc)',
                'Binary (.gpg)',
                'Various line endings (Unix, Windows, Mac)'
            ]
        }
        return report
