use anyhow::Result;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PaymentAddress {
    pub btc_address: String,
    pub xmr_address: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PaymentStatus {
    pub confirmed: bool,
    pub amount_received: u64,
    pub confirmations: u32,
}

pub struct PaymentService {
    btc_rpc_url: String,
    xmr_rpc_url: String,
}

impl PaymentService {
    pub fn new(btc_rpc_url: String, xmr_rpc_url: String) -> Self {
        Self {
            btc_rpc_url,
            xmr_rpc_url,
        }
    }
    
    pub fn generate_escrow_address(&self, order_id: &str) -> PaymentAddress {
        let btc_address = self.generate_btc_address(order_id);
        let xmr_address = self.generate_xmr_address(order_id);
        
        PaymentAddress {
            btc_address,
            xmr_address,
        }
    }
    
    fn generate_btc_address(&self, order_id: &str) -> String {
        use sha2::{Digest, Sha256};
        let mut hasher = Sha256::new();
        hasher.update(order_id.as_bytes());
        let hash = hasher.finalize();
        format!("bc1q{}", hex::encode(&hash[0..20]))
    }
    
    fn generate_xmr_address(&self, order_id: &str) -> String {
        use sha2::{Digest, Sha256};
        let mut hasher = Sha256::new();
        hasher.update(order_id.as_bytes());
        let hash = hasher.finalize();
        let bytes: [u8; 4] = hash[0..4].try_into().unwrap();
        let index = u32::from_le_bytes(bytes);
        format!("subaddress_{}_{}", index / 10000, index % 10000)
    }
    
    pub async fn check_payment_status(&self, _address: &str, _expected_amount: u64) -> Result<PaymentStatus> {
        Ok(PaymentStatus {
            confirmed: false,
            amount_received: 0,
            confirmations: 0,
        })
    }
    
    pub async fn process_payout(
        &self,
        _vendor_id: &str,
        _amount_cents: u64,
        currency: &str,
        _address: &str,
    ) -> Result<String> {
        match currency {
            "btc" => {
                let tx_id = format!("btc_tx_{}", Uuid::new_v4());
                Ok(tx_id)
            }
            "xmr" => {
                let tx_id = format!("xmr_tx_{}", Uuid::new_v4());
                Ok(tx_id)
            }
            _ => Err(anyhow::anyhow!("Unsupported currency")),
        }
    }
    
    async fn cents_to_satoshis(&self, cents: u64) -> Result<u64> {
        Ok(cents * 100)
    }
}
