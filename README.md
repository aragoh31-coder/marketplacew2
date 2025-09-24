# Marketplace Django Application Setup

This is a comprehensive Django marketplace application with cryptocurrency support, security features, and a complete nginx configuration.

## Project Structure

- **Django Application**: Located in the root directory with various apps (accounts, adminpanel, disputes, etc.)
- **Nginx Configuration**: Configured to serve static files and proxy requests to Django
- **Docker Support**: Full Docker Compose setup with PostgreSQL, Redis, and services

## Quick Start

### 1. Environment Setup

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your configuration:
   - Database credentials
   - Redis password
   - Django secret key
   - Cryptocurrency RPC settings (if applicable)

### 2. Start Services

#### Option A: Using the startup script (Recommended)
```bash
./start_services.sh
```

#### Option B: Manual startup
```bash
# Start PostgreSQL and Redis (if using Docker)
docker-compose up -d db redis

# Start Django application
python manage.py migrate --run-syncdb
python manage.py collectstatic --noinput
gunicorn --bind 127.0.0.1:8000 --workers 3 --timeout 120 marketplace.wsgi:application &

# Start nginx (if available)
./start_web_server.sh
```

### 3. Access the Application

- **Web Interface**: http://localhost
- **Django Admin**: http://localhost/admin
- **API Endpoints**: http://localhost/api

## Nginx Configuration

The nginx configuration is set up to:

- **Serve static files** directly from `/workspace/static/`
- **Serve media files** from `/workspace/media/`
- **Proxy API requests** to Django application on port 8000
- **Security headers** for protection against common attacks
- **Gzip compression** for better performance
- **Caching** for improved response times

### Nginx Files:
- `/workspace/nginx/config/nginx.conf` - Main nginx configuration
- `/workspace/nginx/config/sites-available/marketplace` - Site-specific configuration

## Django Applications

- **accounts**: User management and authentication
- **adminpanel**: Administrative interface
- **marketplace**: Core marketplace functionality
- **products**: Product management
- **orders**: Order processing
- **payments**: Payment handling
- **messaging**: User communication
- **disputes**: Dispute resolution
- **vendors**: Vendor management
- **wallets**: Cryptocurrency wallet integration
- **shipping**: Shipping and logistics

## Security Features

- **PGP encryption** for sensitive communications
- **Two-factor authentication**
- **Rate limiting** on API endpoints
- **Security audit logging**
- **Encrypted database fields**
- **HTTPS support** (when SSL is configured)

## Development

### Running Tests
```bash
python manage.py test
```

### Code Quality
```bash
flake8 .
black .
isort .
```

### Database Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

## Production Deployment

1. **Set DEBUG=False** in your environment
2. **Configure proper ALLOWED_HOSTS**
3. **Set up SSL certificates**
4. **Configure firewall rules**
5. **Set up monitoring and logging**
6. **Configure backup procedures**

## Troubleshooting

### Common Issues

1. **Static files not loading**: Run `python manage.py collectstatic`
2. **Database connection issues**: Check database credentials in `.env`
3. **Redis connection issues**: Verify Redis is running and password is correct
4. **Nginx not starting**: Check configuration syntax with `nginx -t`

### Logs

- **Django logs**: Check `/workspace/logs/`
- **Nginx logs**: Check `/workspace/nginx/logs/`
- **Application logs**: Available in the web interface

## Support

For issues and questions, please refer to the security audit reports and cleanup documentation in the repository.

## License

This project is proprietary software.