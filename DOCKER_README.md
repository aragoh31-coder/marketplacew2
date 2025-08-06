# Marketplace Docker Deployment

## Quick Start

1. Extract the Docker package
2. Copy `.env.docker` to `.env` and update the secret keys
3. Run: `./start.sh` or `docker-compose up -d`
4. Access the marketplace at `http://localhost:8000`

## Services

- **web**: Django application (port 8000)
- **db**: PostgreSQL database (port 5432)
- **redis**: Redis cache and message broker (port 6379)
- **celery**: Background task worker
- **celery-beat**: Scheduled task scheduler
- **tor**: Tor proxy for onion service (ports 9050, 8080)

## Environment Configuration

Before deployment, update `.env` with:
- `DJANGO_SECRET_KEY`: Generate a new secret key
- `ENCRYPTION_KEY`: Generate a 32-character Fernet key
- Database credentials if using external database
- Bitcoin/Monero RPC credentials

## Initial Setup

```bash
# Start services
docker-compose up -d

# Run migrations (done automatically)
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Collect static files (done automatically)
docker-compose exec web python manage.py collectstatic --noinput
```

## Tor Configuration

The Tor service automatically creates a hidden service. To get the onion address:

```bash
docker-compose exec tor cat /var/lib/tor/hidden_service/hostname
```

## Monitoring

- View logs: `docker-compose logs -f [service_name]`
- Check service status: `docker-compose ps`
- Monitor Celery tasks: `docker-compose exec celery celery -A marketplace inspect active`

## Security Notes

- Change all default passwords and secret keys
- Use proper SSL/TLS certificates in production
- Configure firewall rules appropriately
- Regularly update Docker images
- Monitor logs for suspicious activity

## Backup

```bash
# Database backup
docker-compose exec db pg_dump -U marketplace marketplace > backup.sql

# Volume backup
docker run --rm -v marketplace_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz /data
```

## Application Features

The marketplace includes:
- User authentication with PGP and TOTP 2FA
- Cryptocurrency wallet system (Bitcoin/Monero)
- Vendor management and product listings
- Order processing and dispute resolution
- Secure messaging system
- Admin panel with triple authentication
- Bot detection and security middleware
- Tor compatibility and onion service

## Troubleshooting

### Common Issues

1. **Database connection errors**: Ensure PostgreSQL is running and credentials are correct
2. **Redis connection errors**: Check Redis service status
3. **Static files not loading**: Run `docker-compose exec web python manage.py collectstatic`
4. **Celery tasks not running**: Check celery worker logs

### Logs

```bash
# View all logs
docker-compose logs

# View specific service logs
docker-compose logs web
docker-compose logs db
docker-compose logs redis
docker-compose logs celery
```

## Production Deployment

For production deployment:

1. Use proper SSL/TLS certificates
2. Configure proper firewall rules
3. Use external database and Redis instances
4. Set up proper backup procedures
5. Monitor system resources and logs
6. Update Docker images regularly
7. Use secrets management for sensitive data

## Development

For development purposes:

```bash
# Use development configuration
docker-compose -f docker-compose.dev.yml up -d

# Access Django shell
docker-compose exec web python manage.py shell

# Run tests
docker-compose exec web python manage.py test
```

## Health Checks

The application includes health checks for all services:

```bash
# Check application health
docker-compose exec web python docker-healthcheck.py

# Check individual service health
docker-compose exec web python manage.py check --database default
docker-compose exec redis redis-cli ping
docker-compose exec db pg_isready -U marketplace
```
