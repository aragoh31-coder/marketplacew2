pub mod auth;
pub mod giftcards;
pub mod payments;
pub mod search;
pub mod admin;

use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Listing {
    pub id: Uuid,
    pub title: String,
    pub description: String,
    pub category: String,
    pub price_cents: i64,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    pub id: String,
    pub title: String,
    pub category: String,
    pub price_cents: u64,
}
