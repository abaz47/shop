#!/bin/bash
# Восстановление HTTPS с уже имеющимися сертификатами.
# Использовать после неудачного запуска init-letsencrypt.sh или когда нужно
# вернуть сайт на HTTPS без получения нового сертификата.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

COMPOSE="docker compose -f docker-compose.prod.yml"

echo ">>> Восстановление HTTPS с существующими сертификатами..."
echo

# 1. Регенерируем HTTPS конфиг из шаблона
if [ ! -f "scripts/generate-nginx-config.sh" ]; then
  echo "✗ Скрипт generate-nginx-config.sh не найден"
  exit 1
fi

bash scripts/generate-nginx-config.sh

# 2. Убираем HTTP-only конфиг, чтобы не было conflicting server name
if [ -f "nginx/conf.d/app-http-only.conf" ]; then
  mv nginx/conf.d/app-http-only.conf nginx/conf.d/app-http-only.conf.disabled
  echo "✓ HTTP-only конфиг отключён"
fi

# 3. Проверяем, что в app.conf есть HTTPS блок
if ! grep -q "listen 443 ssl" nginx/conf.d/app.conf 2>/dev/null; then
  echo "✗ В app.conf нет HTTPS блока."
  echo "  Убедитесь, что в certbot/conf/live/ есть директория с сертификатами (fullchain.pem, privkey.pem)"
  exit 1
fi

# 4. Проверка конфига nginx и перезагрузка
echo ">>> Проверка конфига nginx..."
if $COMPOSE exec -T nginx nginx -t 2>&1; then
  echo "✓ Конфиг корректен"
  echo ">>> Перезагрузка nginx..."
  $COMPOSE exec -T nginx nginx -s reload || $COMPOSE restart nginx
  echo "✓ HTTPS восстановлен"
else
  echo "✗ Ошибка в конфиге nginx. Исправьте конфиг и перезагрузите nginx вручную."
  exit 1
fi

echo
echo "Готово. Сайт должен быть доступен по HTTPS."
