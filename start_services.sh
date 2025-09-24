#!/bin/bash

# Set up environment variables (you should set these in your .env file)
export DJANGO_SETTINGS_MODULE=marketplace.settings
export PYTHONPATH=/workspace:$PYTHONPATH

echo "Starting Django application and Nginx..."

# Function to start Django
start_django() {
    echo "Starting Django application..."
    cd /workspace
    python manage.py migrate --run-syncdb
    python manage.py collectstatic --noinput
    gunicorn --bind 127.0.0.1:8000 --workers 3 --timeout 120 marketplace.wsgi:application &
    DJANGO_PID=$!
    echo "Django started with PID: $DJANGO_PID"
}

# Function to start Nginx
start_nginx() {
    echo "Starting Nginx..."
    cd /workspace
    # Build nginx if needed
    if [ ! -f "nginx-1.26.2/objs/nginx" ]; then
        echo "Building nginx..."
        cd nginx-1.26.2
        ./configure --prefix=/workspace/nginx --with-http_ssl_module --with-http_gzip_static_module
        make
        make install
        cd /workspace
    fi

    # Start nginx
    /workspace/nginx/sbin/nginx -c /workspace/nginx/config/nginx.conf &
    NGINX_PID=$!
    echo "Nginx started with PID: $NGINX_PID"
}

# Function to stop services
stop_services() {
    echo "Stopping services..."
    if [ ! -z "$DJANGO_PID" ]; then
        kill $DJANGO_PID
        echo "Django stopped"
    fi
    if [ ! -z "$NGINX_PID" ]; then
        kill $NGINX_PID
        echo "Nginx stopped"
    fi
}

# Trap to stop services on script exit
trap stop_services EXIT

# Start services
start_django
start_nginx

echo "Services started. Press Ctrl+C to stop."

# Wait for user interrupt
wait