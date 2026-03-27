# Каркас интернет-магазина

## Стек

- **Backend:** Django 6.x (Python 3.12+), Gunicorn
- **Database:** PostgreSQL 16
- **Frontend:** Bootstrap 5 (локально в `static/`)
- **Reverse-proxy:** внешний nginx на хосте + Certbot на хосте
- **Тесты:** pytest, pytest-django, pytest-cov

---

## Локальная разработка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

Тесты: `pytest`

---

## Прод-архитектура

- Docker запускает только приложение и инфраструктуру: `db`, `redis`, `web`, `cdek-widget`, `cleanup-orders`.
- Внешний nginx работает на хосте и слушает `80/443`.
- Внутренние контейнеры доступны только локально:
  - `web`: `127.0.0.1:8000`
  - `cdek-widget`: `127.0.0.1:9000`
- Данные на хосте:
  - `/opt/shop/staticfiles`
  - `/opt/shop/media`
  - `/opt/shop/certbot/www`

---

## Подробная миграция без потерь данных

### 1) Предварительные условия

```bash
sudo apt update
sudo apt install -y nginx certbot
```

Проверьте:
- DNS для `yourdomain.com` и `www.yourdomain.com` указывает на сервер.
- Порты `80/tcp` и `443/tcp` открыты.

### 2) Подготовка проекта и переменных

```bash
cp .env.example .env
nano .env
```

Минимум для прода:

```env
DEBUG=false
DJANGO_SETTINGS_MODULE=config.settings.production
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
ADMIN_EMAIL=admin@yourdomain.com
```

### 3) Создание каталогов на хосте

```bash
sudo mkdir -p /opt/shop/staticfiles /opt/shop/media /opt/shop/certbot/www
```

### 4) Бэкап и перенос текущих данных из Docker volumes

Перед копированием лучше сделать короткое окно обслуживания, чтобы во время переноса никто не загружал новые файлы.

1. Узнайте имена томов:
```bash
docker volume ls | grep -E 'media_files|static_files|postgres_data'
```

2. Перенесите медиа (критично) и статику:
```bash
docker run --rm \
  -v shop_media_files:/from \
  -v /opt/shop/media:/to \
  alpine sh -c "cp -a /from/. /to/"

docker run --rm \
  -v shop_static_files:/from \
  -v /opt/shop/staticfiles:/to \
  alpine sh -c "cp -a /from/. /to/"
```

3. Проверьте, что файлы реально скопировались:
```bash
sudo ls -la /opt/shop/media | head
sudo ls -la /opt/shop/staticfiles | head
```

> Если префикс проекта не `shop`, подставьте фактические имена томов из `docker volume ls`.

### 5) Запуск контейнеров в новой схеме

`docker-compose.prod.yml` уже переведен на bind mounts в `/opt/shop` и loopback-порты.

```bash
docker compose -f docker-compose.prod.yml up -d db redis web cdek-widget cleanup-orders
```

Проверка:
```bash
curl -I http://127.0.0.1:8000/
```

### 6) Включение внешнего nginx и выпуск сертификата

1. Скопируйте боевой конфиг:
```bash
sudo cp nginx/external-yourdomain.com.conf /etc/nginx/sites-available/yourdomain.com.conf
sudo ln -sf /etc/nginx/sites-available/yourdomain.com.conf /etc/nginx/sites-enabled/yourdomain.com.conf
```

2. Для первого выпуска сертификата запустите скрипт:
```bash
chmod +x scripts/init-host-certbot.sh
sudo ./scripts/init-host-certbot.sh admin@yourdomain.com
```

Скрипт:
- включает временный HTTP-only конфиг;
- получает сертификат для `yourdomain.com` и `www.yourdomain.com`;
- переключает nginx на HTTPS-конфиг и перезагружает его.

### 7) Автообновление сертификата

```bash
chmod +x scripts/renew-host-certbot.sh
```

Вариант с cron (ежедневно в 03:17):
```bash
sudo crontab -e
```

Добавьте строку:
```cron
17 3 * * * /bin/bash /opt/shop/app/scripts/renew-host-certbot.sh >> /var/log/letsencrypt-renew.log 2>&1
```

> Замените `/opt/shop/app` на фактический путь к репозиторию.

### 8) Финальная проверка

- Откройте сайт: `https://yourdomain.com`.
- Проверьте старые медиа-файлы в карточках товаров.
- Загрузите новый файл через админку и убедитесь, что он появляется в `/opt/shop/media`.
- Проверьте статику (`/static/...`) и endpoint `service.php`.

---

## Управление

### Обычный запуск

```bash
docker compose -f docker-compose.prod.yml up -d
```

### Обновление приложения

```bash
docker compose -f docker-compose.prod.yml pull web
docker compose -f docker-compose.prod.yml up -d web cleanup-orders
```

### Логи

```bash
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs -f cdek-widget
sudo journalctl -u nginx -f
```

### Остановка

```bash
docker compose -f docker-compose.prod.yml down
```
