#!/bin/bash

LOG_FILE="/var/log/tor_monitor.log"
ONION_ADDRESS="ifx3c72qzfkriijkr3sljmqnagtbtaw3ynvqzr5sxv72rum4ob3cvbqd.onion"
DJANGO_DIR="/home/ubuntu/repos/marketplace"
MAX_RETRIES=3
RETRY_COUNT=0

log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

check_and_restart_tor() {
    if ! systemctl is-active --quiet tor@default; then
        log_message "ERROR: Tor service is down, restarting..."
        sudo systemctl restart tor@default
        sleep 15
        if systemctl is-active --quiet tor@default; then
            log_message "SUCCESS: Tor service restarted"
            RETRY_COUNT=0
        else
            log_message "CRITICAL: Failed to restart Tor service"
            ((RETRY_COUNT++))
        fi
    fi
}

check_and_restart_django() {
    if ! pgrep -f "manage.py runserver" > /dev/null; then
        log_message "ERROR: Django server is down, restarting..."
        cd "$DJANGO_DIR"
        pkill -f "manage.py runserver" 2>/dev/null
        sleep 2
        
        export DJANGO_SECRET_KEY="your-secret-key-here"
        export DATABASE_URL="sqlite:///db.sqlite3"
        export REDIS_URL="redis://localhost:6379/1"
        export CELERY_BROKER_URL="redis://localhost:6379/0"
        export CELERY_RESULT_BACKEND="redis://localhost:6379/0"
        
        nohup /home/ubuntu/.pyenv/versions/3.12.8/bin/python manage.py runserver 127.0.0.1:8000 > /tmp/django.log 2>&1 &
        sleep 10
        if pgrep -f "manage.py runserver" > /dev/null; then
            log_message "SUCCESS: Django server restarted"
        else
            log_message "CRITICAL: Failed to restart Django server - check /tmp/django.log"
        fi
    fi
}

check_onion_connectivity() {
    if ! curl --socks5-hostname 127.0.0.1:9050 -s --connect-timeout 15 "http://$ONION_ADDRESS/" > /dev/null 2>&1; then
        log_message "WARNING: Onion address not accessible, checking services..."
        check_and_restart_tor
        check_and_restart_django
        sleep 20
        if curl --socks5-hostname 127.0.0.1:9050 -s --connect-timeout 15 "http://$ONION_ADDRESS/" > /dev/null 2>&1; then
            log_message "SUCCESS: Onion address restored"
            RETRY_COUNT=0
        else
            log_message "CRITICAL: Onion address still not accessible after restart"
            ((RETRY_COUNT++))
        fi
    else
        log_message "INFO: Onion address is accessible"
        RETRY_COUNT=0
    fi
}

log_message "Starting Tor monitor script"

while true; do
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        log_message "CRITICAL: Max retries reached, waiting 5 minutes before trying again"
        sleep 300
        RETRY_COUNT=0
    fi
    
    check_and_restart_tor
    check_and_restart_django
    check_onion_connectivity
    
    sleep 30
done
