use anyhow::Result;
use dotenvy::dotenv;
use std::env;

#[derive(Debug, Clone)]
pub struct Config {
    pub database_url: String,
    pub redis_url: String,
    pub log_level: String,
    pub master_key: String,
    pub cookie_key: String,
    pub csrf_key: String,
    pub gift_encryption_key: String,
    pub argon2_memory: u32,
    pub argon2_iterations: u32,
    pub argon2_parallelism: u32,
    pub onion_address: Option<String>,
    pub force_tor: bool,
    pub btc_rpc: String,
    pub btc_rpc_user: String,
    pub btc_rpc_pass: String,
    pub xmr_rpc: String,
    pub escrow_timeout_hours: u64,
    pub auto_release: bool,
    pub rate_limit_requests: u32,
    pub rate_limit_window: u64,
    pub pow_difficulty: usize,
    pub enable_search: bool,
    pub enable_recommendations: bool,
    pub enable_2fa: bool,
    pub require_2fa_admin: bool,
    pub metrics_enabled: bool,
    pub sentry_dsn: Option<String>,
}

impl Config {
    pub fn load() -> Result<Self> {
        Ok(Self {
            database_url: env::var("DATABASE_URL")
                .unwrap_or_else(|_| "postgres://postgres:password@localhost/marketplace".to_string()),
            redis_url: env::var("REDIS_URL")
                .unwrap_or_else(|_| "redis://localhost:6379/0".to_string()),
            log_level: env::var("LOG_LEVEL").unwrap_or_else(|_| "info".to_string()),
            master_key: env::var("MASTER_KEY")
                .unwrap_or_else(|_| "default_master_key_change_in_production".to_string()),
            cookie_key: env::var("COOKIE_KEY")
                .unwrap_or_else(|_| "default_cookie_key_change_in_production".to_string()),
            csrf_key: env::var("CSRF_KEY")
                .unwrap_or_else(|_| "default_csrf_key_change_in_production".to_string()),
            gift_encryption_key: env::var("GIFT_ENCRYPTION_KEY")
                .unwrap_or_else(|_| "default_gift_key_change_in_production".to_string()),
            argon2_memory: env::var("ARGON2_MEMORY")
                .unwrap_or_else(|_| "65536".to_string())
                .parse()
                .unwrap_or(65536),
            argon2_iterations: env::var("ARGON2_ITERATIONS")
                .unwrap_or_else(|_| "4".to_string())
                .parse()
                .unwrap_or(4),
            argon2_parallelism: env::var("ARGON2_PARALLELISM")
                .unwrap_or_else(|_| "2".to_string())
                .parse()
                .unwrap_or(2),
            onion_address: env::var("ONION_ADDRESS").ok(),
            force_tor: env::var("FORCE_TOR").is_ok(),
            btc_rpc: env::var("BTC_RPC")
                .unwrap_or_else(|_| "http://localhost:8332".to_string()),
            btc_rpc_user: env::var("BTC_RPC_USER")
                .unwrap_or_else(|_| "bitcoin".to_string()),
            btc_rpc_pass: env::var("BTC_RPC_PASS")
                .unwrap_or_else(|_| "password".to_string()),
            xmr_rpc: env::var("XMR_RPC")
                .unwrap_or_else(|_| "http://localhost:18082/json_rpc".to_string()),
            escrow_timeout_hours: env::var("ESCROW_TIMEOUT_HOURS")
                .unwrap_or_else(|_| "24".to_string())
                .parse()
                .unwrap_or(24),
            auto_release: env::var("AUTO_RELEASE").is_ok(),
            rate_limit_requests: env::var("RATE_LIMIT_REQUESTS")
                .unwrap_or_else(|_| "30".to_string())
                .parse()
                .unwrap_or(30),
            rate_limit_window: env::var("RATE_LIMIT_WINDOW")
                .unwrap_or_else(|_| "60".to_string())
                .parse()
                .unwrap_or(60),
            pow_difficulty: env::var("POW_DIFFICULTY")
                .unwrap_or_else(|_| "20".to_string())
                .parse()
                .unwrap_or(20),
            enable_search: env::var("ENABLE_SEARCH").unwrap_or_else(|_| "true".to_string()) == "true",
            enable_recommendations: env::var("ENABLE_RECOMMENDATIONS").unwrap_or_else(|_| "true".to_string()) == "true",
            enable_2fa: env::var("ENABLE_2FA").unwrap_or_else(|_| "true".to_string()) == "true",
            require_2fa_admin: env::var("REQUIRE_2FA_ADMIN").unwrap_or_else(|_| "true".to_string()) == "true",
            metrics_enabled: env::var("METRICS_ENABLED").unwrap_or_else(|_| "true".to_string()) == "true",
            sentry_dsn: env::var("SENTRY_DSN").ok(),
        })
    }
}

pub fn init_env() -> Result<()> {
    dotenv().ok();
    Ok(())
}
