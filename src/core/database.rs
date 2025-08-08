use anyhow::Result;
use redis::Client as RedisClient;
// use sqlx::{postgres::PgPoolOptions, PgPool};
use crate::core::config::Config;

// pub async fn init(config: &Config) -> Result<PgPool> {
//     let pool = PgPoolOptions::new()
//         .max_connections(20)
//         .connect(&config.database_url)
//         .await?;
//     
//     Ok(pool)
// }

pub fn init_redis(config: &Config) -> Result<RedisClient> {
    let client = RedisClient::open(config.redis_url.as_str())?;
    Ok(client)
}
