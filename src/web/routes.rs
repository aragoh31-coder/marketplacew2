use axum::{
    extract::{Query, State},
    http::StatusCode,
    response::{Html, IntoResponse},
    routing::{get, post},
    Json, Router,
};
use serde::Deserialize;
use crate::web::AppState;

#[derive(Deserialize)]
pub struct SearchQuery {
    q: Option<String>,
    limit: Option<usize>,
}

pub fn public_routes() -> Router<AppState> {
    Router::new()
        .route("/", get(index))
        .route("/health", get(health))
        .route("/search", get(search))
        .route("/metrics", get(metrics))
}

pub fn auth_routes() -> Router<AppState> {
    Router::new()
        .route("/login", get(login_page).post(login))
        .route("/register", get(register_page).post(register))
        .route("/logout", post(logout))
}

pub fn user_routes() -> Router<AppState> {
    Router::new()
        .route("/dashboard", get(dashboard))
        .route("/profile", get(profile))
        .route("/cards", get(my_cards))
}

pub fn admin_routes() -> Router<AppState> {
    Router::new()
        .route("/admin", get(admin_dashboard))
        .route("/admin/users", get(admin_users))
        .route("/admin/stats", get(admin_stats))
}

async fn index() -> impl IntoResponse {
    Html(r#"
    <!DOCTYPE html>
    <html>
    <head>
        <title>Gift Card Marketplace</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .header { background: #333; color: white; padding: 20px; margin: -40px -40px 40px -40px; }
            .card { border: 1px solid #ddd; padding: 20px; margin: 20px 0; border-radius: 8px; }
            .btn { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            .btn:hover { background: #0056b3; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🎁 Gift Card Marketplace</h1>
            <p>Secure, Anonymous, Decentralized</p>
        </div>
        
        <div class="card">
            <h2>Welcome to the Marketplace</h2>
            <p>Buy and sell gift cards securely with cryptocurrency payments.</p>
            <button class="btn" onclick="window.location.href='/search'">Browse Cards</button>
            <button class="btn" onclick="window.location.href='/login'">Login</button>
            <button class="btn" onclick="window.location.href='/register'">Register</button>
        </div>
        
        <div class="card">
            <h3>Features</h3>
            <ul>
                <li>🔒 End-to-end encryption</li>
                <li>🔐 Two-factor authentication</li>
                <li>₿ Bitcoin & Monero payments</li>
                <li>🧅 Tor-only operation</li>
                <li>🛡️ Escrow protection</li>
            </ul>
        </div>
    </body>
    </html>
    "#)
}

async fn health() -> impl IntoResponse {
    Json(serde_json::json!({
        "status": "healthy",
        "timestamp": chrono::Utc::now(),
        "version": "2.0.0"
    }))
}

async fn search(Query(params): Query<SearchQuery>) -> impl IntoResponse {
    let query = params.q.unwrap_or_default();
    let limit = params.limit.unwrap_or(20);
    
    Html(format!(r#"
    <!DOCTYPE html>
    <html>
    <head>
        <title>Search - Gift Card Marketplace</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .header {{ background: #333; color: white; padding: 20px; margin: -40px -40px 40px -40px; }}
            .search-box {{ margin: 20px 0; }}
            .search-box input {{ padding: 10px; width: 300px; border: 1px solid #ddd; border-radius: 4px; }}
            .search-box button {{ padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }}
            .card {{ border: 1px solid #ddd; padding: 20px; margin: 20px 0; border-radius: 8px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔍 Search Gift Cards</h1>
            <a href="/" style="color: white;">← Back to Home</a>
        </div>
        
        <div class="search-box">
            <form method="get">
                <input type="text" name="q" value="{}" placeholder="Search for gift cards...">
                <button type="submit">Search</button>
            </form>
        </div>
        
        <div class="card">
            <h3>Search Results</h3>
            <p>Query: "{}" | Limit: {}</p>
            <p><em>No results found. This is a demo implementation.</em></p>
        </div>
    </body>
    </html>
    "#, query, query, limit))
}

async fn metrics() -> impl IntoResponse {
    let metrics_text = r#"
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/",status="200"} 1

# HELP http_request_duration_seconds HTTP request duration
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{method="GET",path="/",le="0.1"} 1
http_request_duration_seconds_sum{method="GET",path="/"} 0.05
http_request_duration_seconds_count{method="GET",path="/"} 1
"#;
    
    (
        StatusCode::OK,
        [("content-type", "text/plain; version=0.0.4")],
        metrics_text,
    )
}

async fn login_page() -> impl IntoResponse {
    Html(r#"
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login - Gift Card Marketplace</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .header { background: #333; color: white; padding: 20px; margin: -40px -40px 40px -40px; }
            .form { max-width: 400px; margin: 40px auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }
            .form input { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
            .form button { width: 100%; padding: 12px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
            .form button:hover { background: #0056b3; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🔐 Login</h1>
            <a href="/" style="color: white;">← Back to Home</a>
        </div>
        
        <div class="form">
            <h2>Sign In</h2>
            <form method="post">
                <input type="text" name="username" placeholder="Username" required>
                <input type="password" name="password" placeholder="Password" required>
                <input type="text" name="totp_code" placeholder="2FA Code (if enabled)">
                <button type="submit">Login</button>
            </form>
            <p><a href="/register">Don't have an account? Register</a></p>
        </div>
    </body>
    </html>
    "#)
}

async fn register_page() -> impl IntoResponse {
    Html(r#"
    <!DOCTYPE html>
    <html>
    <head>
        <title>Register - Gift Card Marketplace</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .header { background: #333; color: white; padding: 20px; margin: -40px -40px 40px -40px; }
            .form { max-width: 400px; margin: 40px auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }
            .form input { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
            .form button { width: 100%; padding: 12px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; }
            .form button:hover { background: #218838; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📝 Register</h1>
            <a href="/" style="color: white;">← Back to Home</a>
        </div>
        
        <div class="form">
            <h2>Create Account</h2>
            <form method="post">
                <input type="text" name="username" placeholder="Username" required>
                <input type="email" name="email" placeholder="Email" required>
                <input type="password" name="password" placeholder="Password" required>
                <button type="submit">Register</button>
            </form>
            <p><a href="/login">Already have an account? Login</a></p>
        </div>
    </body>
    </html>
    "#)
}

async fn login(State(_state): State<AppState>) -> impl IntoResponse {
    (StatusCode::OK, "Login functionality not implemented in demo")
}

async fn register(State(_state): State<AppState>) -> impl IntoResponse {
    (StatusCode::OK, "Registration functionality not implemented in demo")
}

async fn logout() -> impl IntoResponse {
    (StatusCode::OK, "Logout functionality not implemented in demo")
}

async fn dashboard() -> impl IntoResponse {
    Html(r#"
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard - Gift Card Marketplace</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .header { background: #333; color: white; padding: 20px; margin: -40px -40px 40px -40px; }
            .card { border: 1px solid #ddd; padding: 20px; margin: 20px 0; border-radius: 8px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 Dashboard</h1>
            <a href="/" style="color: white;">← Back to Home</a>
        </div>
        
        <div class="card">
            <h2>Welcome to your Dashboard</h2>
            <p>This is a demo implementation. Full functionality would include:</p>
            <ul>
                <li>Your gift card listings</li>
                <li>Purchase history</li>
                <li>Account settings</li>
                <li>2FA management</li>
            </ul>
        </div>
    </body>
    </html>
    "#)
}

async fn profile() -> impl IntoResponse {
    (StatusCode::OK, "Profile page not implemented in demo")
}

async fn my_cards() -> impl IntoResponse {
    (StatusCode::OK, "My cards page not implemented in demo")
}

async fn admin_dashboard() -> impl IntoResponse {
    Html(r#"
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Dashboard - Gift Card Marketplace</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .header { background: #dc3545; color: white; padding: 20px; margin: -40px -40px 40px -40px; }
            .card { border: 1px solid #ddd; padding: 20px; margin: 20px 0; border-radius: 8px; }
            .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
            .stat { background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>⚙️ Admin Dashboard</h1>
            <a href="/" style="color: white;">← Back to Home</a>
        </div>
        
        <div class="stats">
            <div class="stat">
                <h3>0</h3>
                <p>Total Users</p>
            </div>
            <div class="stat">
                <h3>0</h3>
                <p>Gift Cards</p>
            </div>
            <div class="stat">
                <h3>$0</h3>
                <p>Revenue</p>
            </div>
            <div class="stat">
                <h3>0</h3>
                <p>Transactions</p>
            </div>
        </div>
        
        <div class="card">
            <h2>Admin Functions</h2>
            <p>This is a demo implementation. Full admin panel would include:</p>
            <ul>
                <li>User management</li>
                <li>Gift card moderation</li>
                <li>Transaction monitoring</li>
                <li>System metrics</li>
            </ul>
        </div>
    </body>
    </html>
    "#)
}

async fn admin_users() -> impl IntoResponse {
    (StatusCode::OK, "Admin users page not implemented in demo")
}

async fn admin_stats() -> impl IntoResponse {
    (StatusCode::OK, "Admin stats page not implemented in demo")
}
