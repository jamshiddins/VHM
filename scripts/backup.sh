#!/bin/sh
# scripts/backup.sh

# Настройки
BACKUP_DIR="/backup"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="vendhub_backup_${TIMESTAMP}"
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-30}

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "${GREEN}Starting backup at $(date)${NC}"

# Создание директории для бэкапа
mkdir -p ${BACKUP_DIR}/${BACKUP_NAME}

# 1. Бэкап базы данных
echo "Backing up database..."
pg_dump -h ${PGHOST} -U ${PGUSER} -d ${PGDATABASE} -f ${BACKUP_DIR}/${BACKUP_NAME}/database.sql
if [ $? -eq 0 ]; then
    echo "${GREEN}Database backup completed${NC}"
else
    echo "${RED}Database backup failed${NC}"
    exit 1
fi

# 2. Бэкап конфигурационных файлов
echo "Backing up configuration files..."
cp -r /app/static/uploads ${BACKUP_DIR}/${BACKUP_NAME}/ 2>/dev/null || true
cp -r /app/static/exports ${BACKUP_DIR}/${BACKUP_NAME}/ 2>/dev/null || true

# 3. Создание метаинформации
echo "Creating backup metadata..."
cat > ${BACKUP_DIR}/${BACKUP_NAME}/backup_info.txt <<EOF
Backup created: $(date)
Database: ${PGDATABASE}
Host: $(hostname)
Version: $(cat /app/VERSION 2>/dev/null || echo "unknown")
EOF

# 4. Архивирование
echo "Creating archive..."
cd ${BACKUP_DIR}
tar -czf ${BACKUP_NAME}.tar.gz ${BACKUP_NAME}
rm -rf ${BACKUP_NAME}

# 5. Загрузка в S3 (если настроено)
if [ ! -z "${AWS_S3_BUCKET}" ]; then
    echo "Uploading to S3..."
    aws s3 cp ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz s3://${AWS_S3_BUCKET}/backups/
    if [ $? -eq 0 ]; then
        echo "${GREEN}S3 upload completed${NC}"
    else
        echo "${RED}S3 upload failed${NC}"
    fi
fi

# 6. Удаление старых бэкапов
echo "Cleaning old backups..."
find ${BACKUP_DIR} -name "vendhub_backup_*.tar.gz" -mtime +${RETENTION_DAYS} -delete

echo "${GREEN}Backup completed successfully${NC}"
echo "Backup saved as: ${BACKUP_NAME}.tar.gz"

# 7. Отправка уведомления (опционально)
if [ ! -z "${WEBHOOK_URL}" ]; then
    curl -X POST ${WEBHOOK_URL} \
        -H "Content-Type: application/json" \
        -d "{\"text\":\"Backup completed: ${BACKUP_NAME}.tar.gz\"}"
fi