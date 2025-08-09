#!/bin/bash

echo "🚀 Starting Marketplace Docker Deployment"

if [ ! -f .env ]; then
    echo "📝 Copying .env.docker to .env"
    cp .env.docker .env
    echo "⚠️  Please update .env with your production secrets before continuing"
    echo "Press Enter to continue..."
    read
fi

echo "🔨 Building Docker images..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

echo "⏳ Waiting for database..."
sleep 15

echo "📊 Checking service status..."
docker-compose ps

echo "✅ Marketplace is ready!"
echo "🌐 Access at: http://localhost:8000"
echo "📊 Admin at: http://localhost:8000/admin/"
echo "🔍 Logs: docker-compose logs -f"
echo "🧅 Tor onion address: docker-compose exec tor cat /var/lib/tor/hidden_service/hostname"
echo ""
echo "📝 Next steps:"
echo "1. Create superuser: docker-compose exec web python manage.py createsuperuser"
echo "2. Check logs: docker-compose logs -f"
echo "3. Monitor services: docker-compose ps"
