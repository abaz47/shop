# Интернет-магазин

## Стек

- **Backend:** Django 6.x (Python 3.12+), Gunicorn
- **DB:** PostgreSQL 16
- **Frontend:** Bootstrap 5 (локально в `static/`)
- **Reverse-proxy:** nginx + Let's Encrypt (certbot)
- **Tests:** pytest, pytest-django, pytest-cov

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

## Деплой на сервер

### Шаг 1. Подготовка сервера

```bash
# Установить Docker и Docker Compose (если не установлены)
# Убедиться, что порты 80 и 443 открыты в файрволе
```

### Шаг 2. Клонирование и настройка

```bash
git clone <URL_РЕПОЗИТОРИЯ> shop
cd shop
cp .env.example .env
nano .env
```

**Обязательно заполнить в `.env`:**
```env
SECRET_KEY=secret-key-50-characters-long
DEBUG=false
ALLOWED_HOSTS=yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com

POSTGRES_USER=user
POSTGRES_PASSWORD=password
POSTGRES_DB=shop_db

DJANGO_SETTINGS_MODULE=config.settings.production

# SSL/Let's Encrypt
ADMIN_EMAIL=admin@yourdomain.com
SSL_STAGING=0  # 0 = боевой сертификат, 1 = тестовый
```

### Шаг 3. Получение SSL-сертификата и запуск

```bash
chmod +x scripts/init-letsencrypt.sh
./scripts/init-letsencrypt.sh
```

Скрипт автоматически:
- Генерирует конфиги nginx из шаблонов
- Получает SSL-сертификат Let's Encrypt
- Запускает все контейнеры (db, web, nginx, certbot)

### Шаг 4. Создание суперпользователя

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

Админка: `https://yourdomain.com/admin/`

---

## Управление

### Обычный запуск (после первоначальной настройки)

```bash
docker compose -f docker-compose.prod.yml up -d
```

### Обновление кода приложения

```bash
docker compose -f docker-compose.prod.yml pull web
docker compose -f docker-compose.prod.yml up -d web
```

### Логи

```bash
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs -f nginx
docker compose -f docker-compose.prod.yml logs -f certbot
```

### Остановка

```bash
docker compose -f docker-compose.prod.yml down
```

---

## Автоматическое обновление SSL-сертификатов

Контейнер `certbot` автоматически обновляет SSL-сертификаты каждые 12 часов и перезагружает nginx. Никаких действий не требуется.
