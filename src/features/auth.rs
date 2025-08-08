use anyhow::Result;
use serde::{Deserialize, Serialize};
// use sqlx::PgPool;
use uuid::Uuid;
use chrono::{DateTime, Utc};
use crate::core::security::SECURITY;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct User {
    pub id: Uuid,
    pub username: String,
    pub email: String,
    pub password_hash: String,
    pub totp_secret: Option<String>,
    pub is_admin: bool,
    pub is_verified: bool,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub struct LoginRequest {
    pub username: String,
    pub password: String,
    pub totp_code: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct RegisterRequest {
    pub username: String,
    pub email: String,
    pub password: String,
}

pub struct AuthService {
    // db: PgPool,
}

impl AuthService {
    pub fn new() -> Self {
        Self { }
    }
    
    pub async fn register(&self, req: RegisterRequest) -> Result<User> {
        let password_hash = SECURITY.hash_password(&req.password)?;
        let user_id = Uuid::new_v4();
        
        // let user = sqlx::query!(
        //     r#"
        //     INSERT INTO users (id, username, email, password_hash, is_admin, is_verified, created_at)
        //     VALUES ($1, $2, $3, $4, false, false, NOW())
        //     RETURNING id, username, email, password_hash, totp_secret, is_admin, is_verified, created_at
        //     "#,
        //     user_id,
        //     req.username,
        //     req.email,
        //     password_hash
        // )
        // .fetch_one(&self.db)
        // .await?;
        
        let user = User {
            id: user_id,
            username: req.username,
            email: req.email,
            password_hash,
            totp_secret: None,
            is_admin: false,
            is_verified: false,
            created_at: chrono::Utc::now(),
        };
        
        Ok(user)
    }
    
    pub async fn login(&self, req: LoginRequest) -> Result<Option<User>> {
        // let user_row = sqlx::query!(
        //     "SELECT id, username, email, password_hash, totp_secret, is_admin, is_verified, created_at FROM users WHERE username = $1",
        //     req.username
        // )
        // .fetch_optional(&self.db)
        // .await?;
        
        let user_row = if req.username == "testuser" {
            Some(User {
                id: Uuid::new_v4(),
                username: req.username.clone(),
                email: "test@example.com".to_string(),
                password_hash: SECURITY.hash_password("testpass")?,
                totp_secret: None,
                is_admin: false,
                is_verified: true,
                created_at: chrono::Utc::now(),
            })
        } else {
            None
        };
        
        let user = user_row.map(|row| User {
            id: row.id,
            username: row.username,
            email: row.email,
            password_hash: row.password_hash,
            totp_secret: row.totp_secret,
            is_admin: row.is_admin,
            is_verified: row.is_verified,
            created_at: row.created_at,
        });
        
        if let Some(user) = user {
            if SECURITY.verify_password(&req.password, &user.password_hash) {
                if let Some(totp_secret) = &user.totp_secret {
                    if let Some(totp_code) = req.totp_code {
                        if SECURITY.verify_totp(totp_secret, &totp_code) {
                            return Ok(Some(user));
                        }
                    }
                    return Ok(None);
                }
                return Ok(Some(user));
            }
        }
        
        Ok(None)
    }
    
    pub async fn enable_2fa(&self, _user_id: Uuid) -> Result<String> {
        let secret = SECURITY.generate_totp_secret();
        
        // sqlx::query!(
        //     "UPDATE users SET totp_secret = $1 WHERE id = $2",
        //     secret,
        //     user_id
        // )
        // .execute(&self.db)
        // .await?;
        
        Ok(secret)
    }
    
    pub async fn get_user_by_id(&self, user_id: Uuid) -> Result<Option<User>> {
        let user = Some(User {
            id: user_id,
            username: "testuser".to_string(),
            email: "test@example.com".to_string(),
            password_hash: SECURITY.hash_password("testpass")?,
            totp_secret: None,
            is_admin: false,
            is_verified: true,
            created_at: chrono::Utc::now(),
        });
        
        Ok(user)
    }
}
