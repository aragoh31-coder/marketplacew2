use anyhow::Result;
use serde::{Deserialize, Serialize};
// use sqlx::PgPool;
use uuid::Uuid;
use chrono::{DateTime, Utc};
use crate::core::security::SECURITY;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GiftCard {
    pub id: Uuid,
    pub vendor_id: Uuid,
    pub title: String,
    pub description: String,
    pub category: String,
    pub brand: String,
    pub denomination: i64,
    pub price_cents: i64,
    pub encrypted_code: String,
    pub is_sold: bool,
    pub created_at: DateTime<Utc>,
    pub sold_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Deserialize)]
pub struct CreateGiftCardRequest {
    pub title: String,
    pub description: String,
    pub category: String,
    pub brand: String,
    pub denomination: i64,
    pub price_cents: i64,
    pub gift_code: String,
}

pub struct GiftCardService {
    // db: PgPool,
}

impl GiftCardService {
    pub fn new() -> Self {
        Self { }
    }
    
    pub async fn create_gift_card(&self, vendor_id: Uuid, req: CreateGiftCardRequest) -> Result<GiftCard> {
        let encrypted_code = SECURITY.encrypt_gift_code(&req.gift_code)?;
        let card_id = Uuid::new_v4();
        
        // let card_row = sqlx::query!(...)
        let gift_card = GiftCard {
            id: card_id,
            vendor_id,
            title: req.title.clone(),
            description: req.description.clone(),
            category: req.category.clone(),
            brand: req.brand.clone(),
            denomination: req.denomination,
            price_cents: req.price_cents,
            encrypted_code: encrypted_code.clone(),
            is_sold: false,
            created_at: chrono::Utc::now(),
            sold_at: None,
        };
        
        
        Ok(gift_card)
    }
    
    pub async fn get_available_cards(&self, _limit: i64, _offset: i64) -> Result<Vec<GiftCard>> {
        let cards: Vec<GiftCard> = vec![];
        Ok(cards)
    }
    
    pub async fn get_card_by_id(&self, _card_id: Uuid) -> Result<Option<GiftCard>> {
        // let card_row = sqlx::query!(...)
        let card: Option<GiftCard> = None;
        
        
        Ok(card)
    }
    
    pub async fn purchase_card(&self, _card_id: Uuid, _buyer_id: Uuid) -> Result<String> {
        // let mut tx = self.db.begin().await?;
        
        // let card_row = sqlx::query!(...)
        let card: Option<GiftCard> = None;
        
        
        if let Some(card) = card {
            let decrypted_code = SECURITY.decrypt_gift_code(&card.encrypted_code)?;
            Ok(decrypted_code)
        } else {
            Err(anyhow::anyhow!("Gift card not available"))
        }
    }
    
    pub async fn get_cards_by_category(&self, _category: &str, _limit: i64) -> Result<Vec<GiftCard>> {
        let cards: Vec<GiftCard> = vec![];
        Ok(cards)
    }
}
