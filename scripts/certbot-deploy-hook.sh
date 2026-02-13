#!/bin/sh
# Скрипт для автоматической перезагрузки nginx после обновления сертификата
# Используется как --deploy-hook для certbot renew
# 
# Требования:
# - Docker socket должен быть смонтирован в контейнер certbot: /var/run/docker.sock
# - Имя контейнера nginx должно содержать "nginx" (по умолчанию: shop-nginx-1)

echo ">>> [certbot-deploy-hook] Обновление сертификата завершено, перезагрузка nginx..."

# Ищем контейнер nginx по имени (обычно содержит "nginx")
NGINX_CONTAINER=$(docker ps --format "{{.Names}}" | grep -i nginx | head -1)

if [ -z "$NGINX_CONTAINER" ]; then
  echo "⚠️  [certbot-deploy-hook] Контейнер nginx не найден"
  echo "    Перезагрузите nginx вручную: docker compose -f docker-compose.prod.yml exec nginx nginx -s reload"
  exit 0
fi

# Пробуем перезагрузить nginx через reload (graceful)
if docker exec "$NGINX_CONTAINER" nginx -s reload 2>/dev/null; then
  echo "✓ [certbot-deploy-hook] Nginx успешно перезагружен (reload)"
  exit 0
fi

# Если reload не сработал, пробуем restart контейнера
echo "⚠️  [certbot-deploy-hook] Reload не удался, пробуем restart контейнера..."
if docker restart "$NGINX_CONTAINER" 2>/dev/null; then
  echo "✓ [certbot-deploy-hook] Контейнер nginx перезапущен"
  exit 0
fi

# Если ничего не помогло
echo "⚠️  [certbot-deploy-hook] Не удалось автоматически перезагрузить nginx"
echo "    Перезагрузите вручную: docker compose -f docker-compose.prod.yml exec nginx nginx -s reload"
exit 0
