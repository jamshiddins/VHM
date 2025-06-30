#!/bin/bash
# deploy.sh - Production deployment script

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN} VendHub Production Deployment${NC}"
echo "=================================="

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo "Please copy .env.production to .env and fill in the values"
    exit 1
fi

# Загрузка переменных окружения
export $(cat .env | grep -v '^#' | xargs)

# 1. Проверка Docker и Docker Compose
echo -e "\n${YELLOW}Checking Docker installation...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed!${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Docker Compose is not installed!${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker and Docker Compose are installed${NC}"

# 2. Создание необходимых директорий
echo -e "\n${YELLOW}Creating directories...${NC}"
mkdir -p nginx/ssl
mkdir -p backup
mkdir -p logs
mkdir -p static/uploads
mkdir -p static/exports
mkdir -p monitoring/grafana/dashboards
chmod +x scripts/backup.sh

echo -e "${GREEN}✓ Directories created${NC}"

# 3. Генерация самоподписанного сертификата (для тестирования)
if [ ! -f nginx/ssl/fullchain.pem ]; then
    echo -e "\n${YELLOW}Generating self-signed SSL certificate...${NC}"
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout nginx/ssl/privkey.pem \
        -out nginx/ssl/fullchain.pem \
        -subj "/C=UZ/ST=Tashkent/L=Tashkent/O=VendHub/CN=vendhub.uz"
    echo -e "${GREEN} SSL certificate generated${NC}"
fi

# 4. Сборка образов
echo -e "\n${YELLOW}Building Docker images...${NC}"
docker-compose -f docker-compose.production.yml build --no-cache

# 5. Запуск базы данных и Redis
echo -e "\n${YELLOW}Starting database services...${NC}"
docker-compose -f docker-compose.production.yml up -d postgres redis

# Ожидание готовности БД
echo -e "${YELLOW}Waiting for database to be ready...${NC}"
sleep 10

# 6. Инициализация базы данных
echo -e "\n${YELLOW}Initializing database...${NC}"
docker-compose -f docker-compose.production.yml run --rm backend alembic upgrade head
docker-compose -f docker-compose.production.yml run --rm backend python scripts/init_db.py

# 7. Создание админ пользователя
echo -e "\n${YELLOW}Creating admin user...${NC}"
docker-compose -f docker-compose.production.yml run --rm backend python scripts/create_admin.py

# 8. Запуск всех сервисов
echo -e "\n${YELLOW}Starting all services...${NC}"
docker-compose -f docker-compose.production.yml up -d

# 9. Проверка статуса
echo -e "\n${YELLOW}Checking services status...${NC}"
sleep 10
docker-compose -f docker-compose.production.yml ps

# 10. Проверка health endpoints
echo -e "\n${YELLOW}Checking health endpoints...${NC}"
sleep 5

# Backend health check
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN} Backend is healthy${NC}"
else
    echo -e "${RED} Backend health check failed${NC}"
fi

# Frontend health check
if curl -f http://localhost:3000 > /dev/null 2>&1; then
    echo -e "${GREEN} Frontend is healthy${NC}"
else
    echo -e "${RED} Frontend health check failed${NC}"
fi

# Nginx health check
if curl -f http://localhost/health > /dev/null 2>&1; then
    echo -e "${GREEN} Nginx is healthy${NC}"
else
    echo -e "${RED} Nginx health check failed${NC}"
fi

# 11. Настройка cron для бэкапов
echo -e "\n${YELLOW}Setting up backup cron job...${NC}"
(crontab -l 2>/dev/null; echo "0 3 * * * cd $(pwd) && docker-compose -f docker-compose.production.yml exec -T backup /backup.sh") | crontab -

echo -e "\n${GREEN} Deployment completed successfully!${NC}"
echo -e "\nServices available at:"
echo -e "  - Frontend: https://vendhub.uz"
echo -e "  - API: https://api.vendhub.uz"
echo -e "  - Grafana: http://vendhub.uz:3001 (admin/${GRAFANA_PASSWORD})"
echo -e "  - Prometheus: http://vendhub.uz:9090"

echo -e "\n${YELLOW}Next steps:${NC}"
echo "1. Configure your domain DNS to point to this server"
echo "2. Set up Let's Encrypt SSL certificates"
echo "3. Configure firewall rules"
echo "4. Set up monitoring alerts"
echo "5. Configure backup to external storage"

echo -e "\n${YELLOW}Useful commands:${NC}"
echo "  docker-compose -f docker-compose.production.yml logs -f [service_name]"
echo "  docker-compose -f docker-compose.production.yml restart [service_name]"
echo "  docker-compose -f docker-compose.production.yml exec backend bash"