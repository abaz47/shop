# Каркас интернет-магазина

## Стек

- **Backend:** Django 6.x (Python 3.12+), Gunicorn
- **БД:** PostgreSQL 16
- **Frontend:** Bootstrap 5 (локально в `static/`)
- **Reverse-proxy:** nginx (контейнер) + Let's Encrypt (certbot)
- **Тесты:** pytest, pytest-django, pytest-cov

## Структура

```
config/                  — настройки Django (base / development / production)
core/                    — главная, настройки сайта, юр. страницы, контекст
static/                  — Bootstrap, CSS, изображения
templates/               — базовый шаблон, страницы
tests/                   — общие тесты
nginx/conf.d/app.conf    — конфигурация nginx
scripts/                 — скрипт инициализации SSL
docker-compose.yml       — разработка (Django + Postgres)
docker-compose.prod.yml  — продакшен (Django + Postgres + nginx + certbot)
```

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

## Сборка и публикация образа в Docker Hub

На машине разработки (после тестов и коммитов):

```bash
# 1. Создать миграции, если были изменения в моделях
python manage.py makemigrations

# 2. Войти в Docker Hub (один раз)
docker login

# 3. Собрать образ приложения
docker build -t abaz47/shop-web:latest .

# Опционально: тег с версией (например, по дате или git tag)
# docker tag abaz47/shop-web:latest abaz47/shop-web:2025.02.05

# Опубликовать в Docker Hub
docker push abaz47/shop-web:latest
```

На продакшене образ берётся из Hub (`image: abaz47/shop-web:latest`), локальная сборка не нужна.

---

## Деплой на VPS (пошаговая инструкция)

### Требования

- VPS с Ubuntu 22.04+ (или Debian 12+)
- Docker и Docker Compose (`docker compose`)
- Домен, A-запись которого указывает на IP сервера

### Шаг 1. Установить Docker (если ещё не установлен)

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# выйти и зайти заново, чтобы применились права
docker --version
docker compose version
```

### Шаг 2. Склонировать проект и конфиги

На сервере нужны только конфиги (nginx, certbot, .env), не обязательно клонировать весь репозиторий. Минимальный вариант:

```bash
ssh user@IP_СЕРВЕРА
git clone <URL_РЕПОЗИТОРИЯ> shop
cd shop
```

Образ приложения (`abaz47/shop-web:latest`) будет скачан с Docker Hub при первом `docker compose up`.

### Шаг 3. Настроить `.env`

```bash
cp .env.example .env
nano .env
```

Обязательно заполнить:

```env
SECRET_KEY=длинная-случайная-строка-минимум-50-символов
DEBUG=false
ALLOWED_HOSTS=yarmettaktik.shop,www.yarmettaktik.shop

CSRF_TRUSTED_ORIGINS=https://yarmettaktik.shop,https://www.yarmettaktik.shop

POSTGRES_USER=shop
POSTGRES_PASSWORD=надёжный-пароль
POSTGRES_DB=shop_db

DJANGO_SETTINGS_MODULE=config.settings.production
```

### Шаг 4. Настроить домен в nginx

В файле `nginx/conf.d/app.conf` уже прописан домен `yarmettaktik.shop`.
Если домен другой — замените `server_name` и пути к сертификатам.

### Шаг 5. Получить SSL-сертификат и запустить (один раз)

```bash
chmod +x scripts/init-letsencrypt.sh
sudo ./scripts/init-letsencrypt.sh
```

**Важно:** Этот скрипт нужен **только один раз** для первоначального получения SSL-сертификата. После успешного выполнения HTTPS настроен, и больше запускать скрипт не нужно.

Скрипт:
1. Создаёт временный самоподписанный сертификат.
2. Поднимает nginx + web + db.
3. Получает настоящий сертификат Let's Encrypt через ACME-challenge.
4. Перезагружает nginx с боевым сертификатом.

> **Перед запуском** откройте `scripts/init-letsencrypt.sh` и проверьте
> переменные `DOMAINS`, `EMAIL` и `STAGING` (для теста поставьте `STAGING=1`,
> для боевого сертификата — `STAGING=0`).

### Шаг 6. Проверить

```bash
curl -I https://yarmettaktik.shop/
```

Должен быть ответ `200 OK` и заголовок `server: nginx`.
В браузере — зелёный замочек.

### Шаг 7. Создать суперпользователя

```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

Админка: `https://yarmettaktik.shop/admin/`

---

## Управление

### Обычный запуск (после первоначальной настройки)

После первого запуска скрипта `init-letsencrypt.sh` просто запускайте контейнеры:

```bash
cd /opt/shop
docker compose -f docker-compose.prod.yml up -d
```

### Обновление кода приложения

После изменений в коде (после push нового образа в Docker Hub):

```bash
cd /opt/shop
docker compose -f docker-compose.prod.yml pull web
docker compose -f docker-compose.prod.yml up -d web
```

**Примечание:** Если вы изменили зависимости (`requirements.txt`), нужно пересобрать образ и загрузить его в Docker Hub перед обновлением на сервере.

### Другие команды

```bash
cd /opt/shop

# Логи
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs -f nginx
docker compose -f docker-compose.prod.yml logs -f certbot

# Остановка
docker compose -f docker-compose.prod.yml down

# Перезапуск конкретного сервиса
docker compose -f docker-compose.prod.yml restart web
docker compose -f docker-compose.prod.yml restart nginx

# Тесты в контейнере
docker compose -f docker-compose.prod.yml run --rm web pytest
```

### Автоматическое обновление SSL-сертификатов

Контейнер `certbot` автоматически обновляет SSL-сертификаты каждые 12 часов. Никаких действий не требуется — сертификаты обновляются автоматически до истечения срока действия (90 дней).

Проверить статус обновления можно через логи:
```bash
docker compose -f docker-compose.prod.yml logs certbot
```

**Важно:** После обновления сертификата может потребоваться перезагрузка nginx:
```bash
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```
