#!/usr/bin/env bash
# Первичное получение сертификата Let's Encrypt для внешнего nginx (на хосте).
# Запускать на сервере из корня проекта.

set -euo pipefail

DOMAIN="yourdomain.com"
WWW_DOMAIN="www.yourdomain.com"
WEBROOT="/opt/shop/certbot/www"
HTTP_CONF_SRC="nginx/external-yourdomain.com-http-only.conf"
HTTPS_CONF_SRC="nginx/external-yourdomain.com.conf"
SITE_NAME="yourdomain.com.conf"
SITE_AVAILABLE="/etc/nginx/sites-available/${SITE_NAME}"
SITE_ENABLED="/etc/nginx/sites-enabled/${SITE_NAME}"

if [[ "${EUID}" -ne 0 ]]; then
    echo "Запустите скрипт с sudo:"
    echo "  sudo ./scripts/init-host-certbot.sh admin@${DOMAIN}"
    exit 1
fi

if [[ $# -lt 1 ]]; then
    echo "Укажите email для Let's Encrypt."
    echo "Пример:"
    echo "  sudo ./scripts/init-host-certbot.sh admin@${DOMAIN}"
    exit 1
fi

EMAIL="$1"

if [[ ! -f "${HTTP_CONF_SRC}" || ! -f "${HTTPS_CONF_SRC}" ]]; then
    echo "Не найдены nginx-конфиги в проекте."
    echo "Ожидаются файлы:"
    echo "  ${HTTP_CONF_SRC}"
    echo "  ${HTTPS_CONF_SRC}"
    exit 1
fi

echo ">>> Подготовка каталогов в /opt/shop..."
mkdir -p /opt/shop/staticfiles /opt/shop/media "${WEBROOT}"
chown -R www-data:www-data /opt/shop/certbot
chmod -R 755 /opt/shop/certbot

echo ">>> Включаем временный HTTP-only конфиг..."
cp "${HTTP_CONF_SRC}" "${SITE_AVAILABLE}"
ln -sf "${SITE_AVAILABLE}" "${SITE_ENABLED}"
nginx -t
systemctl reload nginx

echo ">>> Получаем сертификат для ${DOMAIN}, ${WWW_DOMAIN}..."
certbot certonly --webroot \
    -w "${WEBROOT}" \
    -d "${DOMAIN}" \
    -d "${WWW_DOMAIN}" \
    --email "${EMAIL}" \
    --agree-tos \
    --no-eff-email

echo ">>> Проверяем TLS-параметры nginx от certbot..."
if [[ ! -f /etc/letsencrypt/options-ssl-nginx.conf ]]; then
    echo "    Загружаем /etc/letsencrypt/options-ssl-nginx.conf"
    curl -fsSL \
        https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf \
        -o /etc/letsencrypt/options-ssl-nginx.conf
fi

if [[ ! -f /etc/letsencrypt/ssl-dhparams.pem ]]; then
    echo "    Загружаем /etc/letsencrypt/ssl-dhparams.pem"
    curl -fsSL \
        https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem \
        -o /etc/letsencrypt/ssl-dhparams.pem
fi

echo ">>> Переключаемся на боевой HTTPS-конфиг..."
cp "${HTTPS_CONF_SRC}" "${SITE_AVAILABLE}"
nginx -t
systemctl reload nginx

echo
echo "Готово: сертификат получен, HTTPS-конфиг включен."
