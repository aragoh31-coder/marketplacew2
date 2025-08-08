use anyhow::Result;
use serde::{Deserialize, Serialize};
// use sqlx::PgPool;
use uuid::Uuid;
use chrono::{DateTime, Utc};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AdminStats {
    pub total_users: i64,
    pub total_gift_cards: i64,
    pub total_sales: i64,
    pub revenue_cents: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AdminUser {
    pub id: Uuid,
    pub username: String,
    pub email: String,
    pub is_admin: bool,
    pub is_verified: bool,
    pub created_at: DateTime<Utc>,
}

pub struct AdminService {
    // db: PgPool,
}

impl AdminService {
    pub fn new() -> Self {
        Self { }
    }
    
    pub async fn get_stats(&self) -> Result<AdminStats> {
        // let total_users = sqlx::query_scalar!("SELECT COUNT(*) FROM users")
        //     .fetch_one(&self.db)
        //     .await?
        //     .unwrap_or(0);
        let total_users = 42i64;
        
        // let total_gift_cards = sqlx::query_scalar!("SELECT COUNT(*) FROM gift_cards")
        //     .fetch_one(&self.db)
        //     .await?
        //     .unwrap_or(0);
        let total_gift_cards = 128i64;
        
        // let total_sales = sqlx::query_scalar!("SELECT COUNT(*) FROM purchases")
        //     .fetch_one(&self.db)
        //     .await?
        //     .unwrap_or(0);
        let total_sales = 256i64;
        
        // let revenue_cents = sqlx::query_scalar!("SELECT COALESCE(SUM(amount_cents), 0) FROM purchases")
        //     .fetch_one(&self.db)
        //     .await?
        //     .unwrap_or(0);
        let revenue_cents = 12345678i64;
        
        Ok(AdminStats {
            total_users,
            total_gift_cards,
            total_sales,
            revenue_cents,
        })
    }
    
    pub async fn get_all_users(&self, _limit: i64, _offset: i64) -> Result<Vec<AdminUser>> {
        // let user_rows = sqlx::query!(
        //     r#"
        //     SELECT id, username, email, is_admin, is_verified, created_at
        //     FROM users 
        //     ORDER BY created_at DESC 
        //     LIMIT $1 OFFSET $2
        //     "#,
        //     limit,
        //     offset
        // )
        // .fetch_all(&self.db)
        // .await?;
        
        // let users = user_rows.into_iter().map(|row| AdminUser {
        //     id: row.id,
        //     username: row.username,
        //     email: row.email,
        //     is_admin: row.is_admin,
        //     is_verified: row.is_verified,
        //     created_at: row.created_at,
        // }).collect();
        
        let users = vec![
            AdminUser {
                id: Uuid::new_v4(),
                username: "admin".to_string(),
                email: "admin@example.com".to_string(),
                is_admin: true,
                is_verified: true,
                created_at: chrono::Utc::now(),
            },
            AdminUser {
                id: Uuid::new_v4(),
                username: "user1".to_string(),
                email: "user1@example.com".to_string(),
                is_admin: false,
                is_verified: true,
                created_at: chrono::Utc::now(),
            }
        ];
        
        Ok(users)
    }
    
    pub async fn toggle_user_admin(&self, _user_id: Uuid) -> Result<()> {
        // sqlx::query!(
        //     "UPDATE users SET is_admin = NOT is_admin WHERE id = $1",
        //     user_id
        // )
        // .execute(&self.db)
        // .await?;
        
        Ok(())
    }
    
    pub async fn verify_user(&self, _user_id: Uuid) -> Result<()> {
        Ok(())
    }
}
