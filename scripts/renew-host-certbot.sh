#!/usr/bin/env bash
# Обновление сертификатов Let's Encrypt для внешнего nginx (на хосте).
# Можно запускать из cron/systemd timer.

set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Запустите скрипт с sudo:"
    echo "  sudo ./scripts/renew-host-certbot.sh"
    exit 1
fi

echo ">>> Запускаем certbot renew..."
certbot renew --quiet --deploy-hook "systemctl reload nginx"

echo "Готово: сертификаты проверены, nginx перезагружен при необходимости."
