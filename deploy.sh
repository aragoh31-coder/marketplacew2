#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Deploying Hybrid Marketplace..."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

command -v docker >/dev/null 2>&1 || { echo -e "${RED}Docker is required but not installed.${NC}" >&2; exit 1; }
command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 || { echo -e "${RED}Docker Compose is required but not installed.${NC}" >&2; exit 1; }

generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-25
}

if [ ! -f .env.production ]; then
    echo -e "${YELLOW}Generating secure configuration...${NC}"
    
    cp .env.example .env.production
    
    DB_ROOT_PASS=$(generate_password)
    DB_APP_PASS=$(generate_password)
    DB_MIGRATE_PASS=$(generate_password)
    DB_READONLY_PASS=$(generate_password)
    
    REDIS_PASS=$(generate_password)
    
    MASTER_KEY=$(openssl rand -base64 64)
    COOKIE_KEY=$(openssl rand -base64 32)
    CSRF_KEY=$(openssl rand -base64 32)
    GIFT_KEY=$(openssl rand -base64 32)
    
    BTC_RPC_USER=$(generate_password)
    BTC_RPC_PASS=$(generate_password)
    XMR_RPC_USER=$(generate_password)
    XMR_RPC_PASS=$(generate_password)
    
    sed -i "s|AUTOGEN|${DB_APP_PASS}|g" .env.production
    
    cat > .credentials <<EOF
=== MARKETPLACE CREDENTIALS ===
Generated: $(date)

Database Root: ${DB_ROOT_PASS}
Database App: ${DB_APP_PASS}
Redis: ${REDIS_PASS}

Admin Panel: admin / changeme123!
Grafana: admin / changeme

IMPORTANT: Change default passwords after first login!
EOF
    
    echo -e "${GREEN}✓ Configuration generated${NC}"
fi

mkdir -p uploads backups config/prometheus config/grafana/dashboards config/grafana/datasources

cat > config/prometheus.yml <<EOF
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'marketplace'
    static_configs:
      - targets: ['marketplace:8080']
    metrics_path: '/metrics'
EOF

cat > config/grafana/datasources/prometheus.yml <<EOF
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
EOF

echo -e "${YELLOW}Building containers...${NC}"
docker compose build --quiet

echo -e "${YELLOW}Starting services...${NC}"
docker compose up -d

echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
sleep 5

RETRIES=30
while [ $RETRIES -gt 0 ]; do
    if docker compose exec -T marketplace curl -f http://localhost:8080/health >/dev/null 2>&1; then
        echo -e "${GREEN}✓ Marketplace is healthy${NC}"
        break
    fi
    RETRIES=$((RETRIES-1))
    echo -n "."
    sleep 2
done

echo -e "${YELLOW}Waiting for Tor address...${NC}"
sleep 5
ONION_ADDRESS=$(docker compose exec -T tor cat /var/lib/tor/hidden_service/hostname 2>/dev/null | tr -d '\r\n' || echo "pending...")

echo -e "\n${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}🎉 Marketplace Successfully Deployed!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Access Points:${NC}"
echo -e "  Tor:        ${GREEN}http://${ONION_ADDRESS}${NC}"
echo -e "  Local:      ${GREEN}http://localhost:8080${NC}"
echo -e "  Prometheus: ${GREEN}http://localhost:9090${NC}"
echo -e "  Grafana:    ${GREEN}http://localhost:3000${NC}"
echo ""
echo -e "${YELLOW}Default Credentials:${NC}"
echo -e "  Admin Panel: admin / changeme123!"
echo -e "  Grafana:     admin / changeme"
echo ""
echo -e "${RED}⚠ IMPORTANT:${NC}"
echo -e "  1. Save your Tor address: ${ONION_ADDRESS}"
echo -e "  2. Change default passwords immediately"
echo -e "  3. Review .credentials file for all passwords"
echo -e "  4. Enable 2FA for admin accounts"
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"

echo -e "\n${YELLOW}Service Status:${NC}"
docker compose ps

echo -e "\n${YELLOW}View logs:${NC} docker compose logs -f marketplace"
echo -e "${YELLOW}Stop:${NC} docker compose down"
echo -e "${YELLOW}Backup:${NC} ./scripts/backup.sh"
