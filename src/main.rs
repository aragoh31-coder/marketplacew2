mod core;
mod features;
mod web;

use anyhow::Result;
use axum::Router;
use std::net::SocketAddr;
use tokio::signal;
use tower_http::{
    normalize_path::NormalizePathLayer,
    trace::TraceLayer,
};
use tracing::info;

#[tokio::main]
async fn main() -> Result<()> {
    core::config::init_env()?;
    core::security::init_security()?;
    let config = core::config::Config::load()?;
    
    tracing_subscriber::fmt()
        .with_env_filter(&config.log_level)
        .json()
        .init();
    
    // let db = core::database::init(&config).await?;
    // sqlx::migrate!().run(&db).await?;
    
    let redis = core::database::init_redis(&config)?;
    
    let app = Router::new()
        .merge(web::routes::public_routes())
        .merge(web::routes::auth_routes())
        .merge(web::routes::user_routes())
        .merge(web::routes::admin_routes())
        // .layer(web::middleware::security_layer())
        // .layer(RequestBodyLimitLayer::new(5_242_880))
        .layer(NormalizePathLayer::trim_trailing_slash())
        .layer(TraceLayer::new_for_http())
        .with_state(web::AppState { redis, config });
    
    let addr = SocketAddr::from(([0, 0, 0, 0], 8080));
    info!("🚀 Marketplace running on {}", addr);
    
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::Server::from_tcp(listener.into_std()?)
        .unwrap()
        .serve(app.into_make_service())
        .with_graceful_shutdown(shutdown_signal())
        .await?;
    
    Ok(())
}

async fn shutdown_signal() {
    tokio::select! {
        _ = signal::ctrl_c() => {},
        _ = async {
            let mut signal = signal::unix::signal(signal::unix::SignalKind::terminate())
                .expect("failed to install signal handler");
            signal.recv().await
        } => {},
    }
    info!("Graceful shutdown initiated");
}
