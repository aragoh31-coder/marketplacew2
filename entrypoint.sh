#!/bin/bash

echo "Waiting for database..."
while ! nc -z db 5432; do
  sleep 0.1
done
echo "Database started"


echo "Running migrations..."
python manage.py migrate

echo "Setting up staticfiles directory..."
mkdir -p /app/staticfiles
chmod -R 755 /app/staticfiles
chown -R app:app /app/staticfiles

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Checking for superuser..."
python manage.py shell -c "
from django.contrib.auth.models import User
if not User.objects.filter(username='admin').exists():
    print('No admin user found - create one with: docker-compose exec web python manage.py createsuperuser')
else:
    print('Admin user exists')
" 2>/dev/null || echo "Database not ready for superuser check"

echo "Starting application..."
exec "$@"
