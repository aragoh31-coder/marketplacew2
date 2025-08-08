# Axum Gift Card Marketplace

A secure, privacy-focused gift card marketplace built with Rust and Axum framework.

## Features

- 🔒 **Security First**: Argon2id password hashing, AES-256-GCM encryption, TOTP 2FA
- 🧅 **Privacy**: Tor-only operation with .onion addresses
- ₿ **Crypto Payments**: Bitcoin and Monero support with escrow
- 🔍 **Search**: Lightweight search functionality
- 📊 **Monitoring**: Built-in Prometheus metrics and Grafana dashboards
- 🐳 **Easy Deploy**: One-command Docker deployment

## Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd axum-marketplace

# Deploy with Docker (auto-generates all secrets)
./deploy.sh

# Your marketplace will be running in ~60 seconds!
```

## Architecture

- **Core**: Security, configuration, and database management
- **Features**: Authentication, gift cards, payments, search, admin
- **Web**: Routes, middleware, and templates
- **Docker**: Multi-service orchestration with PostgreSQL, Redis, Tor, etc.

## Security Features

- Argon2id password hashing with configurable parameters
- AES-256-GCM encryption for sensitive gift card codes
- TOTP-based two-factor authentication
- Rate limiting and Proof-of-Work challenges
- CSRF protection and security headers
- Least-privilege database roles

## Development

```bash
# Install Rust dependencies
cargo build

# Run locally (requires PostgreSQL and Redis)
cargo run

# Run tests
cargo test

# Check code
cargo clippy
```

## Production Deployment

The `deploy.sh` script handles:
- Auto-generation of secure secrets
- Docker Compose orchestration
- Database migrations
- Health checks
- Tor .onion address generation

## Monitoring

- Prometheus metrics at `/metrics`
- Grafana dashboards (admin/changeme)
- Application logs via Docker Compose
- Automated daily backups

## License

MIT License - see LICENSE file for details.
