import gnupg
import tempfile
import os
import shutil
import logging
import re
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)

class PGPService:
    def __init__(self):
        """Initialize PGP service with temporary GPG directory and enhanced configuration"""
        self.temp_dir = tempfile.mkdtemp(prefix='marketplace_gpg_')
        
        self.gpg = gnupg.GPG(gnupghome=self.temp_dir)
        
        gpg_binary = self._find_gpg_binary()
        if gpg_binary:
            self.gpg.gpgbinary = gpg_binary
        elif hasattr(settings, 'GPG_BINARY'):
            self.gpg.gpgbinary = settings.GPG_BINARY
        
        self._configure_cipher_preferences()
        
        logger.debug(f"PGP Service initialized with temp dir: {self.temp_dir}")
        logger.debug(f"GPG Binary: {self.gpg.gpgbinary}")
        logger.debug(f"GPG Version: {self.gpg.version}")
    
    def _find_gpg_binary(self):
        """Find the best available GPG binary"""
        candidates = ['gpg2', 'gpg', '/usr/bin/gpg2', '/usr/bin/gpg', '/usr/local/bin/gpg']
        for candidate in candidates:
            if shutil.which(candidate):
                logger.debug(f"Found GPG binary: {candidate}")
                return candidate
        return None
    
    def _configure_cipher_preferences(self):
        """Configure GPG for maximum compatibility"""
        try:
            config_content = """
personal-cipher-preferences AES256 AES192 AES CAST5
personal-digest-preferences SHA512 SHA384 SHA256 SHA224 SHA1
personal-compress-preferences ZLIB BZIP2 ZIP Uncompressed
cert-digest-algo SHA256
default-preference-list SHA512 SHA384 SHA256 SHA224 AES256 AES192 AES CAST5 ZLIB BZIP2 ZIP Uncompressed
keyserver-options auto-key-retrieve
trust-model always
"""
            config_path = os.path.join(self.temp_dir, 'gpg.conf')
            with open(config_path, 'w') as f:
                f.write(config_content)
            logger.debug("GPG configuration written for enhanced compatibility")
        except Exception as e:
            logger.warning(f"Could not write GPG config: {e}")
    
    def validate_key_format(self, key_data):
        """Validate and normalize PGP key format"""
        if not key_data or not isinstance(key_data, str):
            return {'success': False, 'error': 'Key data is empty or invalid'}
        
        key_data = key_data.strip()
        
        if not key_data:
            return {'success': False, 'error': 'Key data is empty'}
        
        begin_patterns = [
            r'-----BEGIN PGP PUBLIC KEY BLOCK-----',
            r'-----BEGIN PGP PUBLIC KEY-----',
            r'-----BEGIN PUBLIC KEY-----'
        ]
        
        end_patterns = [
            r'-----END PGP PUBLIC KEY BLOCK-----',
            r'-----END PGP PUBLIC KEY-----',
            r'-----END PUBLIC KEY-----'
        ]
        
        has_begin = any(re.search(pattern, key_data, re.IGNORECASE) for pattern in begin_patterns)
        has_end = any(re.search(pattern, key_data, re.IGNORECASE) for pattern in end_patterns)
        
        if not has_begin or not has_end:
            return {
                'success': False, 
                'error': 'Invalid PGP key format. Key must include BEGIN and END markers.'
            }
        
        lines = key_data.split('\n')
        normalized_lines = []
        in_key_block = False
        
        for line in lines:
            line = line.strip()
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in begin_patterns):
                in_key_block = True
                normalized_lines.append('-----BEGIN PGP PUBLIC KEY BLOCK-----')
            elif any(re.search(pattern, line, re.IGNORECASE) for pattern in end_patterns):
                in_key_block = False
                normalized_lines.append('-----END PGP PUBLIC KEY BLOCK-----')
            elif in_key_block and line:
                if re.match(r'^[A-Za-z0-9+/=]+$', line):
                    normalized_lines.append(line)
                elif line.startswith('=') and re.match(r'^=[A-Za-z0-9+/=]+$', line):
                    normalized_lines.append(line)
                elif line.startswith('Version:') or line.startswith('Comment:') or line.startswith('Hash:'):
                    normalized_lines.append(line)
                elif line and not line.startswith('-'):
                    cleaned_line = ''.join(c for c in line if c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')
                    if cleaned_line and len(cleaned_line) >= 4:
                        normalized_lines.append(cleaned_line)
        
        normalized_key = '\n'.join(normalized_lines)
        
        if len(normalized_lines) < 3:
            return {
                'success': False,
                'error': 'Key appears to be incomplete or corrupted'
            }
        
        return {
            'success': True,
            'normalized_key': normalized_key,
            'original_key': key_data
        }
    
    def _get_algorithm_name(self, algo_id):
        """Convert algorithm ID to readable name"""
        algo_map = {
            '1': 'RSA',
            '16': 'ElGamal (Encrypt-Only)',
            '17': 'DSA',
            '18': 'ECDH',
            '19': 'ECDSA',
            '20': 'ElGamal (Sign & Encrypt)',
            '22': 'EdDSA'
        }
        return algo_map.get(str(algo_id), f'Algorithm {algo_id}')
    
    def _check_key_capabilities(self, key):
        """Check what the key can do"""
        caps = {
            'can_encrypt': False,
            'can_sign': False,
            'can_certify': False,
            'can_authenticate': False,
            'is_expired': False,
            'is_revoked': False,
            'has_encryption_subkey': False
        }
        
        try:
            if key.get('expires'):
                expires_timestamp = int(key['expires'])
                if expires_timestamp > 0:
                    expires_date = datetime.fromtimestamp(expires_timestamp)
                    caps['is_expired'] = expires_date < datetime.now()
            
            caps_str = key.get('caps', '')
            if caps_str:
                caps['can_encrypt'] = 'e' in caps_str.lower()
                caps['can_sign'] = 's' in caps_str.lower()
                caps['can_certify'] = 'c' in caps_str.lower()
                caps['can_authenticate'] = 'a' in caps_str.lower()
            
            subkeys = key.get('subkeys', [])
            for subkey in subkeys:
                if isinstance(subkey, dict):
                    subkey_caps = subkey.get('caps', '')
                    if 'e' in subkey_caps.lower():
                        caps['has_encryption_subkey'] = True
                        caps['can_encrypt'] = True
                        break
                elif isinstance(subkey, list) and len(subkey) > 1:
                    subkey_caps = subkey[1] if len(subkey) > 1 else ''
                    if 'e' in subkey_caps.lower():
                        caps['has_encryption_subkey'] = True
                        caps['can_encrypt'] = True
                        break
            
            if not caps['can_encrypt'] and not caps['has_encryption_subkey']:
                algo = key.get('algo', '')
                if algo in ['1', '16', '18']:
                    caps['can_encrypt'] = True
            
        except Exception as e:
            logger.warning(f"Error checking key capabilities: {e}")
        
        return caps
    
    def _format_subkeys(self, subkeys):
        """Format subkey information"""
        formatted_subkeys = []
        for subkey in subkeys:
            if isinstance(subkey, dict):
                formatted_subkey = {
                    'keyid': subkey.get('keyid', ''),
                    'algorithm': self._get_algorithm_name(subkey.get('algo', '')),
                    'length': subkey.get('length', ''),
                    'capabilities': subkey.get('caps', ''),
                    'created': datetime.fromtimestamp(int(subkey.get('date', 0))).strftime('%Y-%m-%d') if subkey.get('date') else 'Unknown'
                }
            elif isinstance(subkey, list) and len(subkey) >= 4:
                formatted_subkey = {
                    'keyid': subkey[0] if len(subkey) > 0 else '',
                    'algorithm': self._get_algorithm_name(subkey[3]) if len(subkey) > 3 else 'Unknown',
                    'length': subkey[2] if len(subkey) > 2 else '',
                    'capabilities': subkey[1] if len(subkey) > 1 else '',
                    'created': datetime.fromtimestamp(int(subkey[4])).strftime('%Y-%m-%d') if len(subkey) > 4 and subkey[4] else 'Unknown'
                }
            else:
                formatted_subkey = {
                    'keyid': 'Unknown',
                    'algorithm': 'Unknown',
                    'length': 'Unknown',
                    'capabilities': 'Unknown',
                    'created': 'Unknown'
                }
            formatted_subkeys.append(formatted_subkey)
        return formatted_subkeys
    
    def __del__(self):
        """Clean up temporary directory"""
        try:
            import shutil
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.debug(f"Cleaned up temp dir: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temp dir: {e}")
    
    def import_public_key(self, public_key_data):
        """
        Import a public key with enhanced validation and capability detection
        
        Args:
            public_key_data (str): PGP public key block
            
        Returns:
            dict: Import result with success status, fingerprint, and capabilities
        """
        try:
            logger.debug("Validating key format...")
            validation_result = self.validate_key_format(public_key_data)
            
            if not validation_result['success']:
                return {
                    'success': False,
                    'error': validation_result['error']
                }
            
            key_to_import = validation_result['normalized_key']
            
            logger.debug("Importing public key...")
            import_result = self.gpg.import_keys(key_to_import)
            
            if import_result.count > 0:
                fingerprint = import_result.fingerprints[0] if import_result.fingerprints else None
                logger.info(f"Successfully imported key with fingerprint: {fingerprint}")
                
                key_info = self.get_key_info(fingerprint)
                
                result = {
                    'success': True,
                    'fingerprint': fingerprint,
                    'count': import_result.count,
                    'message': f'Successfully imported {import_result.count} key(s)'
                }
                
                if key_info and key_info.get('success'):
                    result.update({
                        'algorithm': key_info.get('algorithm', 'Unknown'),
                        'length': key_info.get('length', 'Unknown'),
                        'capabilities': key_info.get('capabilities', {}),
                        'created': key_info.get('created', 'Unknown'),
                        'expires': key_info.get('expires', 'Never')
                    })
                    
                    caps = key_info.get('capabilities', {})
                    if caps.get('is_expired'):
                        return {
                            'success': False,
                            'error': 'This PGP key has expired and cannot be used'
                        }
                    
                    if caps.get('is_revoked'):
                        return {
                            'success': False,
                            'error': 'This PGP key has been revoked and cannot be used'
                        }
                    
                    if not caps.get('can_encrypt') and not caps.get('has_encryption_subkey'):
                        return {
                            'success': False,
                            'error': 'This key does not support encryption. Please use a key with encryption capability.'
                        }
                
                return result
            else:
                error_msg = str(import_result.stderr) if hasattr(import_result, 'stderr') else 'Unknown error'
                logger.warning(f"No keys were imported: {error_msg}")
                
                if 'invalid' in error_msg.lower():
                    return {
                        'success': False,
                        'error': 'Invalid key format or corrupted key data'
                    }
                elif 'duplicate' in error_msg.lower():
                    return {
                        'success': False,
                        'error': 'This key is already imported'
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Key import failed: {error_msg}'
                    }
                
        except Exception as e:
            logger.error(f"Error importing public key: {e}")
            return {
                'success': False,
                'error': f'Import failed: {str(e)}'
            }
    
    def encrypt_message(self, message, recipient_fingerprint):
        """
        Encrypt a message for a specific recipient with enhanced validation
        
        Args:
            message (str): Plain text message to encrypt
            recipient_fingerprint (str): Recipient's key fingerprint
            
        Returns:
            dict: Encryption result with success status and encrypted message
        """
        try:
            logger.debug(f"Encrypting message for fingerprint: {recipient_fingerprint}")
            
            key_info = self.get_key_info(recipient_fingerprint)
            if key_info and key_info.get('success'):
                caps = key_info.get('capabilities', {})
                
                if caps.get('is_expired'):
                    return {
                        'success': False,
                        'error': 'Cannot encrypt: recipient key has expired'
                    }
                
                if caps.get('is_revoked'):
                    return {
                        'success': False,
                        'error': 'Cannot encrypt: recipient key has been revoked'
                    }
                
                if not caps.get('can_encrypt') and not caps.get('has_encryption_subkey'):
                    return {
                        'success': False,
                        'error': 'Cannot encrypt: recipient key does not support encryption'
                    }
            
            encrypted_data = self.gpg.encrypt(
                message, 
                recipients=[recipient_fingerprint],
                always_trust=True,
                armor=True,
                symmetric=False
            )
            
            if encrypted_data.ok:
                encrypted_message = str(encrypted_data)
                logger.info("Message encrypted successfully")
                logger.debug(f"Encrypted message length: {len(encrypted_message)} bytes")
                
                if encrypted_message.startswith('-----BEGIN PGP MESSAGE-----'):
                    return {
                        'success': True,
                        'encrypted_message': encrypted_message,
                        'fingerprint': recipient_fingerprint
                    }
                else:
                    logger.error("Encrypted data is not in proper PGP format")
                    return {
                        'success': False,
                        'error': 'Encrypted data is not in proper PGP format'
                    }
            else:
                error_msg = str(encrypted_data.stderr)
                logger.error(f"Encryption failed: {error_msg}")
                
                if 'no valid recipients' in error_msg.lower():
                    return {
                        'success': False,
                        'error': 'No valid recipients found. Please check the key fingerprint.'
                    }
                elif 'unusable public key' in error_msg.lower():
                    return {
                        'success': False,
                        'error': 'The public key is not suitable for encryption.'
                    }
                else:
                    return {
                        'success': False,
                        'error': f'Encryption failed: {error_msg}'
                    }
                
        except Exception as e:
            logger.error(f"Error encrypting message: {e}")
            return {
                'success': False,
                'error': f'Encryption error: {str(e)}'
            }
    
    def verify_signature(self, signed_message):
        """
        Verify a PGP signed message
        
        Args:
            signed_message (str): PGP signed message
            
        Returns:
            dict: Verification result with success status and details
        """
        try:
            logger.debug("Verifying PGP signature...")
            
            verified = self.gpg.verify(signed_message)
            
            if verified.valid:
                logger.info(f"Signature verified successfully for key: {verified.key_id}")
                return {
                    'success': True,
                    'valid': True,
                    'key_id': verified.key_id,
                    'fingerprint': verified.fingerprint,
                    'username': verified.username,
                    'message': 'Signature is valid'
                }
            else:
                logger.warning(f"Signature verification failed: {verified.stderr}")
                return {
                    'success': True,
                    'valid': False,
                    'error': verified.stderr or 'Invalid signature',
                    'message': 'Signature is invalid'
                }
                
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return {
                'success': False,
                'error': f'Verification error: {str(e)}'
            }
    
    def extract_message_from_signature(self, signed_message):
        """
        Extract the original message from a clearsigned PGP message
        
        Args:
            signed_message (str): PGP clearsigned message
            
        Returns:
            dict: Extraction result with success status and message
        """
        try:
            logger.debug("Extracting message from PGP signature...")
            
            lines = signed_message.split('\n')
            message_lines = []
            in_message = False
            
            for line in lines:
                if line.startswith('-----BEGIN PGP SIGNED MESSAGE-----'):
                    in_message = True
                    continue
                elif line.startswith('-----BEGIN PGP SIGNATURE-----'):
                    break
                elif in_message and line.startswith('Hash: '):
                    continue
                elif in_message and line.strip() == '':
                    if message_lines:  # Skip empty line after headers
                        message_lines.append(line)
                elif in_message:
                    message_lines.append(line)
            
            extracted_message = '\n'.join(message_lines).strip()
            
            if not extracted_message:
                return {
                    'success': False,
                    'error': 'No message content found in signed message'
                }
            
            logger.info("Message extracted successfully from signature")
            logger.debug(f"Extracted message: {extracted_message[:100]}...")
            
            verification_result = None
            try:
                verification_result = self.verify_signature(signed_message)
                if verification_result.get('valid'):
                    logger.debug("Signature verification successful")
                else:
                    logger.warning("Signature verification failed, but message extracted")
            except Exception as verify_error:
                logger.warning(f"Signature verification error (message still extracted): {verify_error}")
            
            return {
                'success': True,
                'message': extracted_message,
                'verification': verification_result
            }
            
        except Exception as e:
            logger.error(f"Error extracting message from signature: {e}")
            return {
                'success': False,
                'error': f'Extraction error: {str(e)}'
            }
    
    def get_key_info(self, fingerprint):
        """
        Get comprehensive information about a key by fingerprint
        
        Args:
            fingerprint (str): Key fingerprint
            
        Returns:
            dict: Detailed key information including capabilities
        """
        try:
            keys = self.gpg.list_keys()
            for key in keys:
                if key['fingerprint'] == fingerprint:
                    caps = self._check_key_capabilities(key)
                    
                    return {
                        'success': True,
                        'fingerprint': key['fingerprint'],
                        'keyid': key.get('keyid', ''),
                        'uids': key.get('uids', []),
                        'algorithm': self._get_algorithm_name(key.get('algo', '')),
                        'length': key.get('length', ''),
                        'created': datetime.fromtimestamp(int(key.get('date', 0))).strftime('%Y-%m-%d') if key.get('date') else 'Unknown',
                        'expires': datetime.fromtimestamp(int(key.get('expires', 0))).strftime('%Y-%m-%d') if key.get('expires') else 'Never',
                        'capabilities': caps,
                        'subkeys': self._format_subkeys(key.get('subkeys', [])),
                        'trust': key.get('trust', ''),
                        'raw_algo': key.get('algo', ''),
                        'raw_expires': key.get('expires', '')
                    }
            
            return {
                'success': False,
                'error': 'Key not found'
            }
            
        except Exception as e:
            logger.error(f"Error getting key info: {e}")
            return {
                'success': False,
                'error': f'Key info error: {str(e)}'
            }
    
    def test_key_encryption(self, fingerprint):
        """Test if a key can be used for encryption"""
        test_message = "Test encryption message"
        result = self.encrypt_message(test_message, fingerprint)
        return result
    
    def decrypt_message(self, encrypted_message, passphrase=None):
        """Decrypt a PGP message (for testing purposes)"""
        try:
            decrypted_data = self.gpg.decrypt(encrypted_message, passphrase=passphrase)
            
            if decrypted_data.ok:
                return {
                    'success': True,
                    'decrypted_message': str(decrypted_data),
                    'fingerprint': decrypted_data.fingerprint
                }
            else:
                return {
                    'success': False,
                    'error': f'Decryption failed: {decrypted_data.stderr}'
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'Decryption error: {str(e)}'
            }
    
    def verify_signed_message(self, signed_message):
        """Verify a signed message and extract content"""
        try:
            verified = self.gpg.verify(signed_message)
            
            result = {
                'success': True,
                'valid': verified.valid,
                'fingerprint': verified.fingerprint,
                'key_id': verified.key_id,
                'username': verified.username,
                'timestamp': verified.timestamp
            }
            
            if not verified.valid:
                result['error'] = verified.stderr or 'Invalid signature'
            
            return result
            
        except Exception as e:
            return {
                'success': False,
                'error': f'Verification error: {str(e)}'
            }
    
    def create_signed_message(self, message, keyid=None, passphrase=None):
        """Create a clearsigned message (for testing purposes)"""
        try:
            signed_data = self.gpg.sign(message, keyid=keyid, passphrase=passphrase, clearsign=True)
            
            if signed_data:
                return {
                    'success': True,
                    'signed_message': str(signed_data),
                    'fingerprint': signed_data.fingerprint
                }
            else:
                return {
                    'success': False,
                    'error': 'Signing failed'
                }
        except Exception as e:
            return {
                'success': False,
                'error': f'Signing error: {str(e)}'
            }
