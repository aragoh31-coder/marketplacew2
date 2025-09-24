#!/bin/bash

# Simple web server for development
# This script starts a basic HTTP server that serves static files and proxies to Django

echo "Starting development web server..."

# Check if nginx is available
if [ -f "/workspace/nginx/sbin/nginx" ]; then
    echo "Using nginx server..."
    /workspace/nginx/sbin/nginx -c /workspace/nginx/config/nginx.conf
elif command -v python3 &> /dev/null; then
    echo "Using Python HTTP server for static files..."
    echo "Note: This is a development server only. For production, use nginx."

    # Start Python server for static files
    cd /workspace
    python3 -m http.server 80 &
    PYTHON_PID=$!
    echo "Python server started with PID: $PYTHON_PID"
else
    echo "No web server available. Please install nginx or Python3."
    exit 1
fi

# Function to stop services
stop_services() {
    echo "Stopping services..."
    if [ ! -z "$PYTHON_PID" ]; then
        kill $PYTHON_PID 2>/dev/null
        echo "Python server stopped"
    fi

    # Stop nginx if running
    pkill nginx 2>/dev/null
    echo "Nginx stopped"
}

# Trap to stop services on script exit
trap stop_services EXIT

echo "Web server started. Press Ctrl+C to stop."

# Wait for user interrupt
wait