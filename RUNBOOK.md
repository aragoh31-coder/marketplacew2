# Marketplace Docker Stack – Runbook

This repository contains the full Django marketplace application with Dockerized services:
- OpenResty (nginx + Lua gatekeeper)
- Django (Gunicorn)
- Redis
- Postgres
- Tor hidden service (hybrid), with dynamic mapping to OpenResty
- Celery worker and beat

Quick start
1) Copy environment template and fill values:
   cp .env.example .env
   # Optionally also copy .env.docker depending on your workflow

   Important env flags:
   - ALLOWED_HOSTS must include: localhost, 127.0.0.1, django, openresty, and your onion host (if known)
   - ALLOW_INSECURE_ONION_COOKIES=1 for Tor-friendly cookie behavior over HTTP (no Secure flag)
   - POSTGRES_* + REDIS URLs as in .env.example

2) Build and start the stack:
   docker compose build
   docker compose up -d

3) Migrate and collect static:
   docker compose exec -T django python manage.py migrate --noinput
   docker compose exec -T django python manage.py collectstatic --noinput

4) Verify services:
   docker compose ps
   docker compose logs --tail=100 openresty
   docker compose logs --tail=100 django
   docker compose logs --tail=100 tor

5) Access URLs:
   - OpenResty (HTTP): http://127.0.0.1/
   - Django (direct): http://127.0.0.1:8000/ (usually proxied; expect anti-DDoS)
   - Onion: see Tor section below

Anti‑DDoS / No‑JS flow
- Flow: /anti_ddos/spinner/ → /anti_ddos/status/ (auto-PoW) → “/” if verified
- Fallbacks:
  - If autosolve doesn’t finish in time, status redirects to /anti_ddos/pow/.
  - If cookies are blocked, the status endpoint falls back to PoW after a few polls using a client fingerprint.
- Gatekeeper (OpenResty Lua) allows anti_ddos, static, and health paths. Other requests without hmac_token are redirected to /anti_ddos/spinner/.

Tor hidden service
- The tor container dynamically resolves the OpenResty service IP at startup and writes /etc/tor/torrc.
- Hidden service keys are persisted via volume mapping to keep the onion hostname stable across restarts.

Important: Tor keys are not included in this repository.
- The hidden service directory is expected at: /opt/tor/hidden_service on the host, mapped to /var/lib/tor/hidden_service in the container.
- On first start (no keys present), Tor will generate a new hostname; read it with:
    sudo cat /opt/tor/hidden_service/hostname

If you want a stable onion across hosts:
- Copy your hidden_service directory (keys) to /opt/tor/hidden_service on the new host before starting the tor container, with permissions 700 and owner 999:999.

Files to know
- docker-compose.yml: Defines all services and volumes. Tor uses a dynamic startup script.
- Dockerfile, Dockerfile.tor-hybrid: Build images.
- openresty/nginx.conf: OpenResty config; sets headers and loads gatekeeper Lua.
- openresty/lua/antiddos_gatekeeper.lua: Redirect logic based on hmac_token.
- openresty/tor/resolve_and_run.sh: Writes torrc from resolved openresty IP and runs Tor.
- marketplace/settings.py: ALLOWED_HOSTS, cookie flags honoring ALLOW_INSECURE_ONION_COOKIES, ANTIDDOS settings.
- apps/anti_ddos/*: Spinner/Status/PoW/Captcha endpoints and middleware.
- .env.example, .env.docker: Templates for environment variables (no secrets).

Security and cookies over Tor
- When ALLOW_INSECURE_ONION_COOKIES=1, SESSION_COOKIE_SECURE and CSRF_COOKIE_SECURE are disabled so Tor Browser over HTTP can keep session and csrftoken.
- The anti‑DDoS views set hmac_token with Path=/ and without Secure to allow verification over onion HTTP.

Health checks and debugging
- OpenResty: http://127.0.0.1/healthz
- Docker logs:
   docker compose logs --tail=100 openresty
   docker compose logs --tail=100 django
   docker compose logs --tail=100 tor
   docker compose logs --tail=100 celery
- If you see redirect loops, ensure cookies are enabled or expect fallback to PoW after a few seconds.

Postgres schema
- If you have a schema-only dump, restore via:
   docker compose exec -T db psql -U $POSTGRES_USER -d $POSTGRES_DB -f database/schema.sql

Notes
- Do not include real .env or hidden_service keys in version control.
- If you want to test via a public tunnel, ensure ALLOWED_HOSTS includes that host or proxy Host header to “openresty”.
- If ports are in use, stop old stacks or adjust docker-compose ports before up -d.

Troubleshooting
- Tor hostname changing: ensure the /opt/tor/hidden_service volume is mounted and persists; permissions: chmod 700 and chown 999:999.
- DisallowedHost: add your host to ALLOWED_HOSTS or set proxy_set_header Host openresty in nginx.conf.
- Infinite redirects: verify cookie flags and that ALLOW_INSECURE_ONION_COOKIES=1 is set for onion; status should fall back to PoW after a few polls if cookies are blocked.
