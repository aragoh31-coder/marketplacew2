use axum::{
    extract::State,
    http::{Request, StatusCode},
    middleware::Next,
    response::Response,
};
use std::time::{Duration, SystemTime};
use tower::ServiceBuilder;
use tower_http::{
    cors::CorsLayer,
};
use crate::web::AppState;

pub fn security_layer() -> ServiceBuilder<impl tower::Layer<axum::Router> + Clone + Send + 'static> {
    ServiceBuilder::new()
        .layer(CorsLayer::very_permissive())
}

async fn security_headers(req: Request<axum::body::Body>, next: Next<axum::body::Body>) -> Response {
    let mut response = next.run(req).await;
    let headers = response.headers_mut();
    
    if let Ok(value) = "nosniff".parse() {
        headers.insert("X-Content-Type-Options", value);
    }
    if let Ok(value) = "DENY".parse() {
        headers.insert("X-Frame-Options", value);
    }
    if let Ok(value) = "1; mode=block".parse() {
        headers.insert("X-XSS-Protection", value);
    }
    if let Ok(value) = "no-referrer".parse() {
        headers.insert("Referrer-Policy", value);
    }
    if let Ok(value) = "default-src 'self'; script-src 'none'; style-src 'self' 'unsafe-inline'".parse() {
        headers.insert("Content-Security-Policy", value);
    }
    if let Ok(value) = "max-age=31536000; includeSubDomains; preload".parse() {
        headers.insert("Strict-Transport-Security", value);
    }
    if let Ok(value) = "geolocation=(), microphone=(), camera=()".parse() {
        headers.insert("Permissions-Policy", value);
    }
    
    response
}

async fn rate_limit_simple(
    req: Request<axum::body::Body>,
    next: Next<axum::body::Body>,
) -> Result<Response, StatusCode> {
    Ok(next.run(req).await)
}

async fn rate_limit<B>(
    State(_state): State<AppState>,
    req: Request<B>,
    next: Next<B>,
) -> Result<Response, StatusCode> {
    Ok(next.run(req).await)
}

async fn tor_only(req: Request<axum::body::Body>, next: Next<axum::body::Body>) -> Result<Response, StatusCode> {
    Ok(next.run(req).await)
}

async fn csrf_protection(req: Request<axum::body::Body>, next: Next<axum::body::Body>) -> Result<Response, StatusCode> {
    Ok(next.run(req).await)
}

pub async fn metrics_middleware<B>(req: Request<B>, next: Next<B>) -> Response {
    let start = SystemTime::now();
    let _path = req.uri().path().to_string();
    let _method = req.method().to_string();
    
    let response = next.run(req).await;
    
    let _duration = start.elapsed().unwrap_or(Duration::from_secs(0));
    let _status = response.status().as_u16();
    
    response
}
