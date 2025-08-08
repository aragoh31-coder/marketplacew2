pub mod routes;
pub mod middleware;
pub mod templates;

// use sqlx::PgPool;
use redis::Client as RedisClient;
use crate::core::config::Config;

#[derive(Clone)]
pub struct AppState {
    // pub db: PgPool,
    pub redis: RedisClient,
    pub config: Config,
}
