#!/bin/bash
# ─────────────────────────────────────────────────────────────
# Первичное получение SSL-сертификата Let's Encrypt.
# Запускать один раз на сервере из корня проекта:
#   chmod +x scripts/init-letsencrypt.sh
#   sudo ./scripts/init-letsencrypt.sh
# ─────────────────────────────────────────────────────────────
set -e

# Обработка сигналов для корректной остановки
cleanup() {
  echo
  echo ">>> Получен сигнал остановки. Очистка..."
  if [ -n "$CERTBOT_PID" ] && kill -0 "$CERTBOT_PID" 2>/dev/null; then
    echo "    Остановка certbot..."
    kill -TERM "$CERTBOT_PID" 2>/dev/null || true
    sleep 2
    kill -KILL "$CERTBOT_PID" 2>/dev/null || true
  fi
  rm -f /tmp/certbot_exit_code.$$
  exit 130
}

trap cleanup INT TERM

# ── Настройки ──────────────────────────────────────────────
# Домены и email читаются из .env файла
# Если .env не найден или переменные не заданы, используются значения по умолчанию

# Загружаем переменные из .env, если файл существует
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

# Читаем домены из ALLOWED_HOSTS (формат: domain1.com,www.domain1.com,domain2.com)
if [ -n "$ALLOWED_HOSTS" ]; then
  # Преобразуем строку с запятыми в массив, убираем пробелы
  IFS=',' read -ra HOST_ARRAY <<< "$ALLOWED_HOSTS"
  DOMAINS=()
  for host in "${HOST_ARRAY[@]}"; do
    # Убираем пробелы и добавляем в массив
    host=$(echo "$host" | xargs)
    if [ -n "$host" ]; then
      DOMAINS+=("$host")
    fi
  done
else
  # Значения по умолчанию, если ALLOWED_HOSTS не задан
  DOMAINS=(localhost 127.0.0.1)
fi

# Email для уведомлений Let's Encrypt
EMAIL="${ADMIN_EMAIL:-admin@localhost}"

# Режим: 1 = тестовый сертификат (без лимитов), 0 = боевой
STAGING="${SSL_STAGING:-0}"

# ──────────────────────────────────────────────────────────

COMPOSE="docker compose -f docker-compose.prod.yml"
DATA_PATH="./certbot"
RSA_KEY_SIZE=4096

# Проверка, что домены заданы
if [ ${#DOMAINS[@]} -eq 0 ] || [ "${DOMAINS[0]}" = "localhost" ]; then
  echo "⚠️  Ошибка: домены не заданы!"
  echo "    Установите переменную ALLOWED_HOSTS в .env файле"
  echo "    Например: ALLOWED_HOSTS=yarmettaktik.shop,www.yarmettaktik.shop"
  exit 1
fi

# Генерируем конфиги nginx из шаблонов перед началом работы
if [ -f "scripts/generate-nginx-config.sh" ]; then
  echo ">>> Генерация конфигов nginx из шаблонов..."
  bash scripts/generate-nginx-config.sh
  echo
fi

echo
echo "=== Инициализация SSL для ${DOMAINS[*]} ==="
echo "    Email: $EMAIL"
echo "    Staging: $STAGING"
echo

# 1. Каталоги
mkdir -p "$DATA_PATH/conf" "$DATA_PATH/www"

# 2. TLS-параметры (рекомендованные certbot)
if [ ! -e "$DATA_PATH/conf/options-ssl-nginx.conf" ] || \
   [ ! -e "$DATA_PATH/conf/ssl-dhparams.pem" ]; then
  echo ">>> Загрузка рекомендованных TLS-параметров..."
  curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf \
    > "$DATA_PATH/conf/options-ssl-nginx.conf"
  curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem \
    > "$DATA_PATH/conf/ssl-dhparams.pem"
  echo
fi

# 3. Проверка: если уже есть настоящий сертификат, пропускаем
LIVE_PATH="$DATA_PATH/conf/live/${DOMAINS[0]}"
if [ -e "$LIVE_PATH/fullchain.pem" ] && [ -e "$LIVE_PATH/privkey.pem" ]; then
  # Проверяем, не временный ли это сертификат (по CN=localhost)
  if openssl x509 -in "$LIVE_PATH/fullchain.pem" -noout -subject 2>/dev/null | grep -q "CN=localhost"; then
    echo ">>> Найден временный сертификат, будет заменён на настоящий"
  else
    echo ">>> Настоящий сертификат уже существует!"
    echo "    Если нужно обновить, удалите: rm -rf $LIVE_PATH"
    exit 0
  fi
fi

# 4. Временно переключиться на HTTP-only конфиг для получения сертификата
echo ">>> Подготовка HTTP-only конфига для получения сертификата..."

# Генерируем HTTP-only конфиг из шаблона
if [ -f "scripts/generate-nginx-config.sh" ]; then
  bash scripts/generate-nginx-config.sh
fi

HTTP_CONF="nginx/conf.d/app-http-only.conf"
if [ ! -e "$HTTP_CONF" ]; then
  echo "⚠️  Файл $HTTP_CONF не найден!"
  echo "    Убедитесь, что скрипт generate-nginx-config.sh выполнен успешно"
  exit 1
fi

# Резервная копия текущего конфига (если это HTTPS конфиг)
if [ -e "nginx/conf.d/app.conf" ]; then
  # Проверяем, не HTTP-only ли уже используется
  if ! grep -q "listen 443 ssl" "nginx/conf.d/app.conf" 2>/dev/null; then
    echo "ℹ️  Уже используется HTTP-only конфиг, пропускаем переключение"
  else
    if [ ! -e "nginx/conf.d/app.conf.backup" ]; then
      cp nginx/conf.d/app.conf nginx/conf.d/app.conf.backup
      echo "✓ Создана резервная копия HTTPS конфига"
    fi
    # Удалить старый конфиг и скопировать HTTP-only
    rm -f nginx/conf.d/app.conf
    cp "$HTTP_CONF" nginx/conf.d/app.conf
    echo "✓ Переключено на HTTP-only конфиг"
  fi
else
  echo "⚠️  Файл nginx/conf.d/app.conf не найден, используем HTTP-only"
  cp "$HTTP_CONF" nginx/conf.d/app.conf
fi

# Примечание: nginx загружает все .conf файлы в директории
# upstream.conf будет загружен автоматически и доступен для обоих конфигов

# 5. Поднять все контейнеры (web, db, nginx)
echo ">>> Запуск контейнеров..."
$COMPOSE up -d
echo

# Перезапустить nginx, чтобы применить новый конфиг
echo ">>> Перезапуск nginx для применения HTTP-only конфига..."
$COMPOSE restart nginx
echo

# Подождать, пока nginx начнёт отвечать
echo ">>> Ожидание готовности nginx..."
sleep 5

# Проверка статуса контейнера nginx
if ! $COMPOSE ps nginx | grep -q "Up"; then
  echo "✗ Контейнер nginx не запущен!"
  echo "    Логи nginx:"
  $COMPOSE logs nginx --tail 20
  exit 1
fi

# Проверка доступности HTTP (для ACME challenge)
echo ">>> Проверка доступности HTTP и ACME challenge..."
sleep 2

# Проверяем несколько раз с задержкой
HTTP_CODE="000"
for i in {1..5}; do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/.well-known/acme-challenge/test 2>/dev/null || echo "000")
  if [ "$HTTP_CODE" != "000" ]; then
    break
  fi
  echo "    Попытка $i/5..."
  sleep 2
done

if [ "$HTTP_CODE" = "404" ] || [ "$HTTP_CODE" = "200" ]; then
  echo "✓ HTTP доступен (код: $HTTP_CODE)"
elif [ "$HTTP_CODE" = "301" ] || [ "$HTTP_CODE" = "302" ]; then
  echo "⚠️  HTTP редиректит на HTTPS (код: $HTTP_CODE)"
  echo "    Это нормально, если используется HTTPS конфиг вместо HTTP-only"
elif [ "$HTTP_CODE" = "000" ]; then
  echo "✗ HTTP недоступен (nginx не отвечает)"
  echo "    Проверка логов nginx:"
  $COMPOSE logs nginx --tail 30 2>/dev/null | tail -20
  echo
  echo "    Проверка конфига nginx:"
  $COMPOSE exec nginx nginx -t 2>&1 || true
  exit 1
else
  echo "⚠️  HTTP вернул неожиданный код: $HTTP_CODE"
  echo "    Проверка логов nginx:"
  $COMPOSE logs nginx --tail 10 2>/dev/null | grep -i error || echo "    (ошибок не найдено)"
fi

# Проверка доступности домена извне (для Let's Encrypt)
echo ">>> Проверка DNS..."
DNS_OK=true
# Используем host или nslookup вместо dig (dig может быть не установлен)
for domain in "${DOMAINS[@]}"; do
  if command -v host >/dev/null 2>&1; then
    DOMAIN_IP=$(host "$domain" | grep "has address" | awk '{print $4}' | head -1)
  elif command -v nslookup >/dev/null 2>&1; then
    DOMAIN_IP=$(nslookup "$domain" | grep -A1 "Name:" | grep "Address:" | awk '{print $2}' | head -1)
  else
    # Fallback: используем getent или просто пропускаем проверку
    DOMAIN_IP=$(getent hosts "$domain" | awk '{print $1}' | head -1)
  fi
  
  if [ -n "$DOMAIN_IP" ]; then
    SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s icanhazip.com 2>/dev/null || echo "")
    echo "✓ DNS для $domain: $DOMAIN_IP"
    if [ -n "$SERVER_IP" ] && [ "$DOMAIN_IP" != "$SERVER_IP" ]; then
      echo "  ⚠️  IP домена ($DOMAIN_IP) не совпадает с IP сервера ($SERVER_IP)"
      echo "      Это нормально, если используется CDN или прокси"
    fi
  else
    echo "⚠️  Не удалось проверить DNS для $domain (команды dig/host/nslookup недоступны)"
    echo "    Проверьте вручную: host $domain или nslookup $domain"
    # Не блокируем выполнение, если DNS-проверка не удалась
  fi
done

# Не блокируем выполнение из-за проблем с DNS-проверкой
# (команды могут быть недоступны, но DNS может быть настроен)

# Проверка доступности ACME challenge извне
echo ">>> Проверка доступности ACME challenge извне..."
TEST_FILE="acme-test-$$"

# Убедимся, что директория существует и файл создан правильно
# nginx ищет файлы в /var/www/certbot/.well-known/acme-challenge/
mkdir -p "$DATA_PATH/www/.well-known/acme-challenge"
echo "test" > "$DATA_PATH/www/.well-known/acme-challenge/$TEST_FILE"
chmod 644 "$DATA_PATH/www/.well-known/acme-challenge/$TEST_FILE" 2>/dev/null || true

# Проверяем, что файл виден в контейнере nginx
echo "    Проверка доступности файла в контейнере nginx..."
sleep 2
if $COMPOSE exec -T nginx test -f "/var/www/certbot/$TEST_FILE" 2>/dev/null; then
  echo "✓ Файл доступен в контейнере nginx"
else
  echo "⚠️  Файл не найден в контейнере nginx"
  echo "    Проверка монтирования volume..."
  $COMPOSE exec -T nginx ls -la /var/www/certbot/ 2>/dev/null || echo "    Не удалось проверить"
fi

sleep 1

# Проверка файрвола и портов
echo ">>> Диагностика файрвола и портов..."
if command -v ufw >/dev/null 2>&1; then
  echo "    UFW статус:"
  ufw status | grep -E "80|443" || echo "      Порты 80/443 не найдены в правилах UFW"
elif command -v firewall-cmd >/dev/null 2>&1; then
  echo "    Firewalld статус:"
  firewall-cmd --list-ports 2>/dev/null | grep -E "80|443" || echo "      Порты 80/443 не найдены в правилах firewalld"
elif command -v iptables >/dev/null 2>&1; then
  echo "    iptables правила для портов 80/443:"
  iptables -L -n | grep -E ":80|:443" || echo "      Правила для портов 80/443 не найдены"
else
  echo "    Файрвол не найден (ufw/firewalld/iptables)"
fi

# Проверка, слушает ли nginx на внешнем интерфейсе
echo ">>> Проверка прослушивания портов..."
if command -v netstat >/dev/null 2>&1; then
  netstat -tlnp | grep -E ":80|:443" || echo "    Порты 80/443 не слушаются"
elif command -v ss >/dev/null 2>&1; then
  ss -tlnp | grep -E ":80|:443" || echo "    Порты 80/443 не слушаются"
fi

echo

# Проверяем, что файл создан и доступен
ACME_TEST_PATH="$DATA_PATH/www/.well-known/acme-challenge/$TEST_FILE"
if [ ! -f "$ACME_TEST_PATH" ]; then
  echo "✗ Ошибка: тестовый файл не создан в $ACME_TEST_PATH"
  ACME_OK=false
else
  echo "✓ Тестовый файл создан: $ACME_TEST_PATH"
  echo "    Содержимое: $(cat "$ACME_TEST_PATH")"
fi

ACME_OK=true
for domain in "${DOMAINS[@]}"; do
  ACME_URL="http://$domain/.well-known/acme-challenge/$TEST_FILE"
  echo "    Проверка $ACME_URL..."
  
  # Проверяем с таймаутом и подробным выводом
  RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}\nTIME:%{time_total}" --max-time 10 "$ACME_URL" 2>&1)
  HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
  TIME=$(echo "$RESPONSE" | grep "TIME" | cut -d: -f2)
  BODY=$(echo "$RESPONSE" | grep -v "HTTP_CODE" | grep -v "TIME")
  
  if echo "$BODY" | grep -q "test"; then
    echo "✓ ACME challenge доступен для $domain (код: $HTTP_CODE, время: ${TIME}s)"
  elif [ "$HTTP_CODE" = "404" ]; then
    echo "⚠️  ACME challenge вернул 404 для $domain"
    echo "      Проверка файла в контейнере nginx:"
    $COMPOSE exec -T nginx ls -la /var/www/certbot/.well-known/acme-challenge/ 2>/dev/null || echo "      Не удалось проверить"
    echo "      Проверка файла на хосте:"
    ls -la "$ACME_TEST_PATH" 2>/dev/null || echo "      Файл не найден"
    echo "      Проверка конфига nginx:"
    $COMPOSE exec -T nginx cat /etc/nginx/conf.d/app.conf 2>/dev/null | grep -A5 "acme-challenge" || echo "      Не удалось проверить"
    echo "      ⚠️  Это может быть проблемой - certbot ожидает найти файл"
    echo "      Но продолжим - certbot создаст файл сам при проверке"
    # Не блокируем - certbot сам создаст файлы при проверке
  elif [ "$HTTP_CODE" = "000" ] || [ -z "$HTTP_CODE" ]; then
    echo "✗ ACME challenge недоступен для $domain (нет соединения)"
    echo "      Возможные причины:"
    echo "      - Порты 80/443 закрыты в файрволе"
    echo "      - Провайдер блокирует входящие соединения"
    echo "      - Проблемы с маршрутизацией"
    ACME_OK=false
  else
    echo "⚠️  ACME challenge вернул код $HTTP_CODE для $domain"
    echo "      Ответ: $(echo "$BODY" | head -c 100)"
    if [ "$HTTP_CODE" != "200" ]; then
      ACME_OK=false
    fi
  fi
done
rm -f "$ACME_TEST_PATH"

if [ "$ACME_OK" != "true" ]; then
  echo
  echo "⚠️  ACME challenge недоступен извне. Certbot может не пройти проверку."
  echo
  echo "📋 Инструкции по устранению проблемы:"
  echo
  echo "1. Откройте порты 80 и 443 в файрволе:"
  echo
  echo "   Для UFW:"
  echo "     sudo ufw allow 80/tcp"
  echo "     sudo ufw allow 443/tcp"
  echo "     sudo ufw reload"
  echo
  echo "   Для firewalld:"
  echo "     sudo firewall-cmd --permanent --add-service=http"
  echo "     sudo firewall-cmd --permanent --add-service=https"
  echo "     sudo firewall-cmd --reload"
  echo
  echo "   Для iptables:"
  echo "     sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT"
  echo "     sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT"
  echo "     sudo iptables-save"
  echo
  echo "2. Проверьте, что порты открыты в панели управления VPS (если используется)"
  echo
  echo "3. Проверьте доступность извне:"
  echo "     curl -I http://yarmettaktik.shop/.well-known/acme-challenge/test"
  echo
  echo "4. Убедитесь, что:"
  echo "   - DNS настроен: A-запись для домена указывает на IP сервера ($(curl -s ifconfig.me 2>/dev/null || echo 'IP'))"
  echo "   - nginx работает: docker compose -f docker-compose.prod.yml ps nginx"
  echo "   - Порты слушаются: netstat -tlnp | grep -E ':80|:443'"
  echo
  read -p "Продолжить получение сертификата? (y/N) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo
    echo "Запустите скрипт снова после открытия портов."
    exit 1
  fi
fi
echo

# 6. Получить настоящий сертификат Let's Encrypt
echo ">>> Запрос сертификата Let's Encrypt..."

DOMAIN_ARGS=""
for domain in "${DOMAINS[@]}"; do
  DOMAIN_ARGS="$DOMAIN_ARGS -d $domain"
done

STAGING_ARG=""
if [ "$STAGING" != "0" ]; then
  STAGING_ARG="--staging"
fi

echo ">>> Запуск certbot (это может занять 30-60 секунд)..."
echo "    Домены: ${DOMAINS[*]}"
echo "    Email: $EMAIL"
echo "    Staging: $STAGING"
echo

# Собираем команду certbot
# Примечание: --deploy-hook не используется при первоначальном получении,
# так как nginx ещё не настроен на HTTPS. Hook будет работать при обновлении.
CERTBOT_CMD="certbot certonly --webroot \
  -w /var/www/certbot \
  $STAGING_ARG \
  --email $EMAIL \
  --rsa-key-size $RSA_KEY_SIZE \
  --agree-tos \
  --no-eff-email \
  --force-renewal \
  $DOMAIN_ARGS"

echo "Команда: $CERTBOT_CMD"
echo

# Используем timeout для предотвращения зависания (5 минут)
# Также добавляем обработку сигналов для корректной остановки
echo ">>> Запуск certbot (таймаут: 5 минут)..."
echo "    Для остановки нажмите Ctrl+C (может потребоваться несколько раз)"
echo

# Запускаем certbot в фоне с таймаутом и сохраняем PID
CERTBOT_PID=""
(
  $COMPOSE run --rm --entrypoint "" certbot sh -c "$CERTBOT_CMD" 2>&1
  echo $? > /tmp/certbot_exit_code.$$
) &
CERTBOT_PID=$!

# Ждём завершения с таймаутом
TIMEOUT=300
ELAPSED=0
while kill -0 $CERTBOT_PID 2>/dev/null && [ $ELAPSED -lt $TIMEOUT ]; do
  sleep 1
  ELAPSED=$((ELAPSED + 1))
  # Показываем прогресс каждые 10 секунд
  if [ $((ELAPSED % 10)) -eq 0 ]; then
    echo "    Ожидание... (${ELAPSED}s / ${TIMEOUT}s)"
  fi
done

# Проверяем результат
if kill -0 $CERTBOT_PID 2>/dev/null; then
  # Процесс всё ещё работает - убиваем его
  echo "    Таймаут! Останавливаем certbot..."
  kill -TERM $CERTBOT_PID 2>/dev/null
  sleep 2
  kill -KILL $CERTBOT_PID 2>/dev/null
  echo "✗ Certbot превысил таймаут (5 минут)"
  echo "  Проверьте логи выше и попробуйте снова"
  exit 1
fi

# Ждём завершения и получаем код возврата
wait $CERTBOT_PID
EXIT_CODE=${?}

if [ -f /tmp/certbot_exit_code.$$ ]; then
  EXIT_CODE=$(cat /tmp/certbot_exit_code.$$)
  rm -f /tmp/certbot_exit_code.$$
fi

if [ "$EXIT_CODE" = "0" ]; then
  echo "✓ Сертификат получен успешно"
else
  echo "✗ Ошибка получения сертификата (код: $EXIT_CODE)"
  echo "  Проверьте:"
  echo "  1. DNS настроен и указывает на этот сервер"
  echo "  2. Порты 80 и 443 открыты в файрволе"
  echo "  3. nginx доступен извне по HTTP"
  echo "  4. ACME challenge файлы доступны по HTTP"
  echo "  5. Логи certbot выше для деталей"
  exit 1
fi

echo

# 7. Переключиться обратно на HTTPS конфиг и перезагрузить nginx
# Certbot может создать директорию с суффиксом -0001, -0002 и т.д.
# Ищем фактическую директорию с сертификатом
CERT_DIR=""
if [ -e "$LIVE_PATH/fullchain.pem" ] && [ -e "$LIVE_PATH/privkey.pem" ]; then
  CERT_DIR="$LIVE_PATH"
else
  # Ищем директорию с суффиксом
  BASE_DIR="$DATA_PATH/conf/live"
  if [ -d "$BASE_DIR" ]; then
    for dir in "$BASE_DIR"/${DOMAINS[0]}*; do
      if [ -d "$dir" ] && [ -e "$dir/fullchain.pem" ] && [ -e "$dir/privkey.pem" ]; then
        CERT_DIR="$dir"
        echo ">>> Найден сертификат в: $CERT_DIR"
        break
      fi
    done
  fi
fi

if [ -n "$CERT_DIR" ] && [ -e "$CERT_DIR/fullchain.pem" ] && [ -e "$CERT_DIR/privkey.pem" ]; then
  echo ">>> Сертификат получен успешно!"
  echo "    Расположение: $CERT_DIR"
  
  # Обновляем конфиг nginx, если путь отличается от ожидаемого
  CERT_NAME=$(basename "$CERT_DIR")
  if [ "$CERT_NAME" != "${DOMAINS[0]}" ]; then
    echo ">>> Обновление пути к сертификату в конфиге nginx..."
    # Обновим конфиг, если нужно (но обычно certbot создаёт симлинк)
    if [ ! -e "$LIVE_PATH" ] && [ -e "$CERT_DIR" ]; then
      echo "    Certbot создал директорию $CERT_NAME вместо ${DOMAINS[0]}"
      echo "    Это нормально - certbot создаст симлинк при следующем обновлении"
    fi
  fi
  
  # Регенерируем HTTPS конфиг из шаблона с правильным путём к сертификату
  echo ">>> Регенерация HTTPS конфига nginx с обновлённым путём к сертификату..."
  if [ -f "scripts/generate-nginx-config.sh" ]; then
    # Передаём имя директории сертификата в скрипт генерации, если отличается
    if [ "$CERT_NAME" != "${DOMAINS[0]}" ]; then
      export FIRST_DOMAIN_OVERRIDE="$CERT_NAME"
    fi
    bash scripts/generate-nginx-config.sh
    unset FIRST_DOMAIN_OVERRIDE
    echo "✓ HTTPS конфиг nginx регенерирован"
  else
    # Fallback: восстанавливаем из backup, если скрипт генерации не найден
    if [ -e "nginx/conf.d/app.conf.backup" ]; then
      echo ">>> Восстановление HTTPS конфига из backup..."
      rm -f nginx/conf.d/app.conf
      mv nginx/conf.d/app.conf.backup nginx/conf.d/app.conf
      
      # Удалить upstream django из конфига (он теперь в upstream.conf)
      echo ">>> Удаление дублирующего upstream из конфига..."
      sed -i '/^upstream django/,/^}$/d' nginx/conf.d/app.conf
      
      # Обновляем путь к сертификату вручную
      if [ "$CERT_NAME" != "${DOMAINS[0]}" ]; then
        echo ">>> Обновление пути к сертификату в конфиге..."
        sed -i "s|/etc/letsencrypt/live/${DOMAINS[0]}/|/etc/letsencrypt/live/$CERT_NAME/|g" nginx/conf.d/app.conf
        echo "✓ Конфиг обновлён для использования сертификата из $CERT_NAME"
      fi
      echo "✓ HTTPS конфиг восстановлен"
    fi
  fi
  else
    echo "⚠️  Резервная копия HTTPS конфига не найдена"
    echo "    Убедитесь, что nginx/conf.d/app.conf содержит HTTPS блок"
  fi
  
  # Перезагрузить nginx
  echo ">>> Проверка конфига nginx..."
  if $COMPOSE exec -T nginx nginx -t 2>&1; then
    echo "✓ Конфиг nginx корректен"
    echo ">>> Перезагрузка nginx с HTTPS..."
    $COMPOSE exec -T nginx nginx -s reload || $COMPOSE restart nginx
    echo "✓ Nginx перезагружен с HTTPS"
  else
    echo "✗ Ошибка в конфиге nginx!"
    echo "    Проверьте конфиг вручную:"
    echo "    docker compose -f docker-compose.prod.yml exec nginx nginx -t"
    exit 1
  fi
else
  echo "⚠️  Сертификат не найден в ожидаемом месте."
  echo "    Проверьте логи выше и DNS-настройки домена."
  echo "    HTTP-only конфиг оставлен активным для повторной попытки."
  echo "    Искали в: $LIVE_PATH"
  exit 1
fi

echo
echo "=== Готово! HTTPS настроен для ${DOMAINS[*]} ==="
echo "    Сайт: https://${DOMAINS[0]}/"
echo
