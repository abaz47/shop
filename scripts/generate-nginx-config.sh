#!/bin/bash
# Генерация конфигов nginx из шаблонов

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# Загружаем переменные из .env
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# Проверяем наличие ALLOWED_HOSTS
if [ -z "$ALLOWED_HOSTS" ]; then
  echo "⚠️  Ошибка: переменная ALLOWED_HOSTS не задана в .env"
  echo "    Установите её, например: ALLOWED_HOSTS=example.com,www.example.com"
  exit 1
fi

# Преобразуем ALLOWED_HOSTS в формат для nginx server_name
# Формат: domain1.com www.domain1.com domain2.com
NGINX_SERVER_NAME=$(echo "$ALLOWED_HOSTS" | tr ',' ' ' | xargs)

# Определяем путь к сертификату (первый домен из списка)
FIRST_DOMAIN=$(echo "$ALLOWED_HOSTS" | cut -d',' -f1 | xargs)

# Если FIRST_DOMAIN переопределён (например, с суффиксом -0001), используем его
if [ -n "$FIRST_DOMAIN_OVERRIDE" ]; then
  FIRST_DOMAIN="$FIRST_DOMAIN_OVERRIDE"
fi

NGINX_CERT_PATH="/etc/letsencrypt/live/${FIRST_DOMAIN}"

# Проверяем, существует ли сертификат с суффиксом (например, -0001, -0002)
if [ -d "./certbot/conf/live" ]; then
  # Ищем директорию с сертификатом (может быть с суффиксом)
  CERT_DIR=$(find "./certbot/conf/live" -maxdepth 1 -type d -name "${FIRST_DOMAIN}*" | head -1)
  if [ -n "$CERT_DIR" ] && [ -f "$CERT_DIR/fullchain.pem" ]; then
    CERT_DIR_NAME=$(basename "$CERT_DIR")
    NGINX_CERT_PATH="/etc/letsencrypt/live/${CERT_DIR_NAME}"
  fi
fi

echo ">>> Генерация конфигов nginx..."
echo "    Server name: $NGINX_SERVER_NAME"
echo "    Cert path: $NGINX_CERT_PATH"

# Создаём директорию для конфигов, если её нет
mkdir -p nginx/conf.d

# Экспортируем переменные для envsubst
export NGINX_SERVER_NAME
export NGINX_CERT_PATH

# Генерируем конфиги из шаблонов
if [ -f "nginx/conf.d/templates/app.conf.template" ]; then
  envsubst '${NGINX_SERVER_NAME} ${NGINX_CERT_PATH}' < nginx/conf.d/templates/app.conf.template > nginx/conf.d/app.conf
  echo "✓ Сгенерирован nginx/conf.d/app.conf"
else
  echo "⚠️  Шаблон nginx/conf.d/templates/app.conf.template не найден"
fi

if [ -f "nginx/conf.d/templates/app-http-only.conf.template" ]; then
  envsubst '${NGINX_SERVER_NAME} ${NGINX_CERT_PATH}' < nginx/conf.d/templates/app-http-only.conf.template > nginx/conf.d/app-http-only.conf
  echo "✓ Сгенерирован nginx/conf.d/app-http-only.conf"
else
  echo "⚠️  Шаблон nginx/conf.d/templates/app-http-only.conf.template не найден"
fi

echo "✓ Генерация конфигов завершена"
