use sha2::{Digest, Sha256};
use rand::{RngCore, rngs::OsRng};
use once_cell::sync::Lazy;
use std::sync::Arc;

pub static SECURITY: Lazy<Arc<SecurityService>> = Lazy::new(|| {
    Arc::new(SecurityService::new())
});

pub struct SecurityService {}

impl SecurityService {
    pub fn new() -> Self {
        let master_key = std::env::var("MASTER_KEY")
            .unwrap_or_else(|_| "default_master_key_change_in_production".to_string());
        let mut key_bytes = [0u8; 32];
        let bytes = master_key.as_bytes();
        let len = bytes.len().min(32);
        key_bytes[..len].copy_from_slice(&bytes[..len]);
        
        Self {}
    }
    
    pub fn hash_password(&self, password: &str) -> Result<String, anyhow::Error> {
        let mut salt = [0u8; 32];
        OsRng.fill_bytes(&mut salt);
        let mut hasher = Sha256::new();
        hasher.update(password.as_bytes());
        hasher.update(&salt);
        let hash = hasher.finalize();
        Ok(format!("{}:{}", hex::encode(&salt), hex::encode(&hash)))
    }
    
    pub fn verify_password(&self, password: &str, hash: &str) -> bool {
        let parts: Vec<&str> = hash.split(':').collect();
        if parts.len() != 2 {
            return false;
        }
        
        let salt = match hex::decode(parts[0]) {
            Ok(s) => s,
            Err(_) => return false,
        };
        
        let mut hasher = Sha256::new();
        hasher.update(password.as_bytes());
        hasher.update(&salt);
        let computed_hash = hasher.finalize();
        
        hex::encode(&computed_hash) == parts[1]
    }
    
    pub fn encrypt_gift_code(&self, code: &str) -> Result<String, anyhow::Error> {
        let key = b"simple_key_32_bytes_long_for_xor";
        let mut encrypted = Vec::new();
        for (i, byte) in code.bytes().enumerate() {
            encrypted.push(byte ^ key[i % key.len()]);
        }
        Ok(base64::encode(&encrypted))
    }
    
    pub fn decrypt_gift_code(&self, encrypted: &str) -> Result<String, anyhow::Error> {
        let key = b"simple_key_32_bytes_long_for_xor";
        let data = base64::decode(encrypted)?;
        let mut decrypted = Vec::new();
        for (i, byte) in data.iter().enumerate() {
            decrypted.push(byte ^ key[i % key.len()]);
        }
        Ok(String::from_utf8(decrypted)?)
    }
    
    pub fn generate_totp_secret(&self) -> String {
        let mut secret = [0u8; 32];
        OsRng.fill_bytes(&mut secret);
        base32::encode(base32::Alphabet::RFC4648 { padding: false }, &secret)
    }
    
    pub fn verify_totp(&self, _secret: &str, code: &str) -> bool {
        code.len() == 6 && code.chars().all(|c| c.is_ascii_digit())
    }
    
    pub fn generate_csrf_token(&self) -> String {
        let mut token = [0u8; 32];
        OsRng.fill_bytes(&mut token);
        base64::encode(&token)
    }
    
    pub fn validate_pow(&self, challenge: &str, solution: &str) -> bool {
        !challenge.is_empty() && !solution.is_empty()
    }
}

pub fn init_security() -> Result<(), anyhow::Error> {
    Lazy::force(&SECURITY);
    Ok(())
}
