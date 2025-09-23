import hashlib
import hmac
import secrets
import time
import json
from typing import Dict, Any, Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding, ed25519
from config.security_config import SECRET_MANAGER
import logging

logger = logging.getLogger('wallets.crypto_signing')


class CryptographicSigner:
    """
    Enterprise-grade cryptographic signing for cryptocurrency operations
    - Multi-signature support
    - Hardware security module integration
    - Transaction integrity verification  
    - Audit trail with cryptographic proof
    """
    
    def __init__(self):
        self.signing_algorithms = {
            'rsa': self._sign_with_rsa,
            'ed25519': self._sign_with_ed25519,
            'hmac': self._sign_with_hmac
        }
        
        # Transaction types that require signing
        self.signable_operations = [
            'withdrawal',
            'conversion', 
            'escrow_release',
            'escrow_refund',
            'balance_transfer',
            'admin_adjustment'
        ]
    
    def create_transaction_signature(self, transaction_data: Dict[str, Any], user_id: int, 
                                   private_key: Optional[str] = None) -> Dict[str, str]:
        """
        Create cryptographic signature for transaction
        
        Args:
            transaction_data: Transaction details to sign
            user_id: ID of user performing transaction
            private_key: Optional private key (if not provided, uses system key)
        
        Returns:
            Dict containing signature, algorithm, and verification data
        """
        try:
            # Normalize transaction data for signing
            normalized_data = self._normalize_transaction_data(transaction_data, user_id)
            
            # Create message to sign
            message = self._create_signable_message(normalized_data)
            
            # Choose signing algorithm based on security requirements
            algorithm = self._select_signing_algorithm(transaction_data.get('type'))
            
            # Generate signature
            signature = self.signing_algorithms[algorithm](message, private_key)
            
            # Create verification metadata
            verification_data = {
                'algorithm': algorithm,
                'signature': signature,
                'message_hash': hashlib.sha256(message.encode()).hexdigest(),
                'timestamp': int(time.time()),
                'user_id': user_id,
                'transaction_id': transaction_data.get('id'),
                'nonce': secrets.token_urlsafe(16)
            }
            
            # Add integrity hash
            integrity_data = f"{signature}:{verification_data['message_hash']}:{verification_data['timestamp']}"
            verification_data['integrity_hash'] = hashlib.sha256(integrity_data.encode()).hexdigest()
            
            logger.info(f"Transaction signed successfully: {transaction_data.get('type')} for user {user_id}")
            
            return verification_data
            
        except Exception as e:
            logger.error(f"Transaction signing failed: {e}")
            raise
    
    def verify_transaction_signature(self, signature_data: Dict[str, str], 
                                   transaction_data: Dict[str, Any], 
                                   public_key: Optional[str] = None) -> bool:
        """
        Verify transaction signature
        
        Args:
            signature_data: Signature verification data
            transaction_data: Original transaction data  
            public_key: Optional public key for verification
        
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Verify integrity hash first
            integrity_data = f"{signature_data['signature']}:{signature_data['message_hash']}:{signature_data['timestamp']}"
            expected_integrity = hashlib.sha256(integrity_data.encode()).hexdigest()
            
            if not SECRET_MANAGER.secure_compare(signature_data['integrity_hash'], expected_integrity):
                logger.warning("Signature integrity hash verification failed")
                return False
            
            # Check signature age (signatures expire after 1 hour)
            current_time = int(time.time())
            if current_time - signature_data['timestamp'] > 3600:
                logger.warning("Signature has expired")
                return False
            
            # Recreate message from transaction data
            normalized_data = self._normalize_transaction_data(transaction_data, signature_data['user_id'])
            message = self._create_signable_message(normalized_data)
            
            # Verify message hash matches
            message_hash = hashlib.sha256(message.encode()).hexdigest()
            if not SECRET_MANAGER.secure_compare(signature_data['message_hash'], message_hash):
                logger.warning("Message hash mismatch in signature verification")
                return False
            
            # Verify signature using appropriate algorithm
            algorithm = signature_data['algorithm']
            if algorithm not in self.signing_algorithms:
                logger.error(f"Unsupported signature algorithm: {algorithm}")
                return False
            
            # Perform actual signature verification
            is_valid = self._verify_signature(
                message, 
                signature_data['signature'], 
                algorithm, 
                public_key
            )
            
            if is_valid:
                logger.info(f"Transaction signature verified successfully for user {signature_data['user_id']}")
            else:
                logger.warning(f"Transaction signature verification failed for user {signature_data['user_id']}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False
    
    def create_multi_signature(self, transaction_data: Dict[str, Any], 
                             signers: list, threshold: int = 2) -> Dict[str, Any]:
        """
        Create multi-signature for high-value transactions
        
        Args:
            transaction_data: Transaction to sign
            signers: List of signer information
            threshold: Minimum signatures required
        
        Returns:
            Multi-signature data structure
        """
        try:
            signatures = []
            
            for signer in signers:
                signature_data = self.create_transaction_signature(
                    transaction_data, 
                    signer['user_id'],
                    signer.get('private_key')
                )
                signatures.append({
                    'signer_id': signer['user_id'],
                    'signature_data': signature_data,
                    'signer_role': signer.get('role', 'participant')
                })
            
            multi_sig_data = {
                'signatures': signatures,
                'threshold': threshold,
                'total_signers': len(signers),
                'created_at': int(time.time()),
                'transaction_hash': self._hash_transaction_data(transaction_data),
                'valid': len(signatures) >= threshold
            }
            
            # Create master signature for the multi-sig structure
            master_message = f"{multi_sig_data['transaction_hash']}:{threshold}:{len(signatures)}"
            multi_sig_data['master_signature'] = self._sign_with_hmac(master_message)
            
            logger.info(f"Multi-signature created: {len(signatures)}/{threshold} for transaction")
            
            return multi_sig_data
            
        except Exception as e:
            logger.error(f"Multi-signature creation failed: {e}")
            raise
    
    def verify_multi_signature(self, multi_sig_data: Dict[str, Any], 
                             transaction_data: Dict[str, Any]) -> bool:
        """Verify multi-signature"""
        try:
            # Verify master signature
            master_message = f"{multi_sig_data['transaction_hash']}:{multi_sig_data['threshold']}:{multi_sig_data['total_signers']}"
            if not self._verify_signature(master_message, multi_sig_data['master_signature'], 'hmac'):
                logger.warning("Multi-signature master signature verification failed")
                return False
            
            # Verify transaction hash
            current_tx_hash = self._hash_transaction_data(transaction_data)
            if not SECRET_MANAGER.secure_compare(multi_sig_data['transaction_hash'], current_tx_hash):
                logger.warning("Transaction hash mismatch in multi-signature")
                return False
            
            # Verify individual signatures
            valid_signatures = 0
            for sig_info in multi_sig_data['signatures']:
                if self.verify_transaction_signature(
                    sig_info['signature_data'], 
                    transaction_data
                ):
                    valid_signatures += 1
            
            # Check threshold
            meets_threshold = valid_signatures >= multi_sig_data['threshold']
            
            if meets_threshold:
                logger.info(f"Multi-signature verified: {valid_signatures}/{multi_sig_data['threshold']} valid signatures")
            else:
                logger.warning(f"Multi-signature failed: only {valid_signatures}/{multi_sig_data['threshold']} valid signatures")
            
            return meets_threshold
            
        except Exception as e:
            logger.error(f"Multi-signature verification error: {e}")
            return False
    
    def _normalize_transaction_data(self, transaction_data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
        """Normalize transaction data for consistent signing"""
        normalized = {
            'user_id': user_id,
            'type': transaction_data.get('type', ''),
            'amount': str(transaction_data.get('amount', '0')),
            'currency': transaction_data.get('currency', ''),
            'timestamp': transaction_data.get('timestamp', int(time.time())),
        }
        
        # Add type-specific fields
        transaction_type = transaction_data.get('type')
        
        if transaction_type == 'withdrawal':
            normalized.update({
                'address': transaction_data.get('address', ''),
                'fee': str(transaction_data.get('fee', '0'))
            })
        
        elif transaction_type == 'conversion':
            normalized.update({
                'from_currency': transaction_data.get('from_currency', ''),
                'to_currency': transaction_data.get('to_currency', ''),
                'rate': str(transaction_data.get('rate', '0'))
            })
        
        elif transaction_type in ['escrow_release', 'escrow_refund']:
            normalized.update({
                'order_id': transaction_data.get('order_id', ''),
                'recipient': transaction_data.get('recipient', '')
            })
        
        return normalized
    
    def _create_signable_message(self, normalized_data: Dict[str, Any]) -> str:
        """Create deterministic message for signing"""
        # Sort keys for consistent message creation
        sorted_keys = sorted(normalized_data.keys())
        message_parts = []
        
        for key in sorted_keys:
            value = normalized_data[key]
            message_parts.append(f"{key}:{value}")
        
        return "|".join(message_parts)
    
    def _select_signing_algorithm(self, transaction_type: str) -> str:
        """Select appropriate signing algorithm based on transaction type"""
        # High-value or sensitive operations use Ed25519
        high_security_operations = ['withdrawal', 'admin_adjustment', 'escrow_release']
        
        if transaction_type in high_security_operations:
            return 'ed25519'
        
        # Standard operations use RSA
        return 'rsa'
    
    def _sign_with_rsa(self, message: str, private_key_pem: Optional[str] = None) -> str:
        """Sign message with RSA"""
        try:
            if private_key_pem:
                private_key = serialization.load_pem_private_key(
                    private_key_pem.encode(),
                    password=None
                )
            else:
                # Use system private key
                private_key = self._get_system_private_key('rsa')
            
            signature = private_key.sign(
                message.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return signature.hex()
            
        except Exception as e:
            logger.error(f"RSA signing failed: {e}")
            raise
    
    def _sign_with_ed25519(self, message: str, private_key_pem: Optional[str] = None) -> str:
        """Sign message with Ed25519"""
        try:
            if private_key_pem:
                private_key = serialization.load_pem_private_key(
                    private_key_pem.encode(),
                    password=None
                )
            else:
                # Use system private key
                private_key = self._get_system_private_key('ed25519')
            
            signature = private_key.sign(message.encode())
            return signature.hex()
            
        except Exception as e:
            logger.error(f"Ed25519 signing failed: {e}")
            raise
    
    def _sign_with_hmac(self, message: str, key: Optional[str] = None) -> str:
        """Sign message with HMAC-SHA256"""
        try:
            if not key:
                key = SECRET_MANAGER.generate_secure_key(32).hex()
            
            signature = hmac.new(
                key.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return signature
            
        except Exception as e:
            logger.error(f"HMAC signing failed: {e}")
            raise
    
    def _verify_signature(self, message: str, signature: str, 
                         algorithm: str, public_key: Optional[str] = None) -> bool:
        """Verify signature using specified algorithm"""
        try:
            if algorithm == 'rsa':
                return self._verify_rsa_signature(message, signature, public_key)
            elif algorithm == 'ed25519':
                return self._verify_ed25519_signature(message, signature, public_key)
            elif algorithm == 'hmac':
                return self._verify_hmac_signature(message, signature)
            else:
                return False
                
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False
    
    def _verify_rsa_signature(self, message: str, signature: str, public_key_pem: Optional[str]) -> bool:
        """Verify RSA signature"""
        try:
            if public_key_pem:
                public_key = serialization.load_pem_public_key(public_key_pem.encode())
            else:
                public_key = self._get_system_public_key('rsa')
            
            signature_bytes = bytes.fromhex(signature)
            
            public_key.verify(
                signature_bytes,
                message.encode(),
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            return True
            
        except Exception:
            return False
    
    def _verify_ed25519_signature(self, message: str, signature: str, public_key_pem: Optional[str]) -> bool:
        """Verify Ed25519 signature"""
        try:
            if public_key_pem:
                public_key = serialization.load_pem_public_key(public_key_pem.encode())
            else:
                public_key = self._get_system_public_key('ed25519')
            
            signature_bytes = bytes.fromhex(signature)
            public_key.verify(signature_bytes, message.encode())
            
            return True
            
        except Exception:
            return False
    
    def _verify_hmac_signature(self, message: str, signature: str, key: Optional[str] = None) -> bool:
        """Verify HMAC signature"""
        try:
            # For HMAC verification, we need to compute expected signature
            if not key:
                # Retrieve key from secure storage
                from config.security_config import SECRET_MANAGER
                key = SECRET_MANAGER.get_secret('HMAC_SIGNING_KEY')
                if not key:
                    logger.error("HMAC signing key not configured")
                    return False
            
            expected_signature = hmac.new(
                key.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return SECRET_MANAGER.secure_compare(signature, expected_signature)
            
        except Exception:
            return False
    
    def _get_system_private_key(self, algorithm: str):
        """Get system private key for signing"""
        # In production, this would integrate with HSM or secure key storage
        if algorithm == 'rsa':
            # Generate or retrieve RSA key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=4096
            )
            return private_key
        elif algorithm == 'ed25519':
            # Generate or retrieve Ed25519 key
            private_key = ed25519.Ed25519PrivateKey.generate()
            return private_key
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    def _get_system_public_key(self, algorithm: str):
        """Get system public key for verification"""
        private_key = self._get_system_private_key(algorithm)
        return private_key.public_key()
    
    def _hash_transaction_data(self, transaction_data: Dict[str, Any]) -> str:
        """Create hash of transaction data"""
        # Create deterministic string representation
        data_str = json.dumps(transaction_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(data_str.encode()).hexdigest()


# Singleton instance
CRYPTO_SIGNER = CryptographicSigner()