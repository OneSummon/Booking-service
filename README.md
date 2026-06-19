# Booking Service

Асинхронный REST API сервис бронирования отелей на базе FastAPI. Реализует полный цикл - от поиска отеля и бронирования номера до онлайн-оплаты через ЮКассу.

---

## Содержание

- [Технологии](#технологии)
- [Архитектура](#архитектура)
- [Возможности](#возможности)
- [Модели данных](#модели-данных)
- [API эндпоинты](#api-эндпоинты)
- [Фоновые задачи](#фоновые-задачи)
- [Безопасность](#безопасность)
- [Тестирование](#тестирование)
- [Быстрый старт](#быстрый-старт)
- [Переменные окружения](#переменные-окружения)

---

## Технологии

| Слой | Инструмент |
|---|---|
| Фреймворк | FastAPI 0.136, Python 3.12 |
| База данных | PostgreSQL 15 + SQLAlchemy 2.0 (async) + asyncpg |
| Миграции | Alembic |
| Кэширование | Redis + fastapi-cache2 |
| Очередь задач | Celery + Celery Beat + Redis |
| Аутентификация | JWT (access + refresh токены), bcrypt, python-jose |
| Платежи | ЮКасса SDK |
| Rate limiting | slowapi (Redis storage) |
| Валидация | Pydantic v2 |
| Логирование | structlog-style + Correlation ID middleware |
| Прокси | Nginx |
| Контейнеризация | Docker + Docker Compose |
| Тесты | pytest + pytest-asyncio |

---

## Архитектура

```
                    ┌───────────────┐
                    │     Nginx     │  :80
                    └──────┬────────┘
                           │
                    ┌──────▼────────┐
                    │   FastAPI     │  :8000
                    │   (uvicorn)   │
                    └──┬──────┬─────┘
                       │      │
          ┌────────────▼──┐  ┌▼──────────────┐
          │  PostgreSQL   │  │     Redis     │
          │  (основные    │  │  кэш / лимиты │
          │   данные)     │  │  / задачи     │
          └───────────────┘  └───────┬───────┘
                                     │
                       ┌─────────────▼──────────────────┐
                       │  Celery Worker + Beat          │
                       │  (фоновые задачи по расписанию)│
                       └────────────────────────────────┘
```

Приложение построено по слоистой архитектуре:

- **routers/** - HTTP обработчики, валидация входных данных
- **services/** - бизнес-логика, работа с БД
- **schemas/** - Pydantic-схемы запросов и ответов
- **database/models.py** - SQLAlchemy ORM-модели
- **celery_app.py** - периодические фоновые задачи

---

## Возможности

### Аутентификация
- Регистрация и вход по email/паролю
- Пара токенов: короткий access token (JWT) + долгоживущий refresh token
- Ротация refresh-токена при каждом обновлении
- Отзыв токенов при выходе и смене пароля
- Ограничение количества активных сессий

### Отели и номера
- Поиск отелей с фильтрацией (город, страна, звёздность)
- Получение детальной информации об отеле
- Просмотр типов номеров и их характеристик
- Проверка доступности номера на конкретные даты

### Бронирование
- Создание бронирования с автоматическим расчётом стоимости
- Защита от двойного бронирования через `SELECT ... FOR UPDATE`
- Просмотр своих бронирований с фильтрацией по статусу
- Отмена бронирования с указанием причины
- Автоматическая отмена неоплаченных бронирований

### Платежи (ЮКасса)
- Создание платёжной сессии и получение URL для оплаты
- Обработка webhook-уведомлений от ЮКассы
- Автоматическое обновление статусов бронирования при успешной оплате
- Отмена платежа при отмене бронирования

### Панель администратора
- Создание, редактирование и скрытие отелей
- Управление типами номеров
- Просмотр всех бронирований с пагинацией
- Отмена любого бронирования

### Профиль пользователя
- Просмотр и редактирование профиля
- Смена пароля (с автоматическим отзывом всех токенов)
- Удаление аккаунта

---

## Модели данных

```
User
├── id, email, password_hash
├── first_name, last_name
├── role (user | admin)
└── bookings[]

Hotel
├── id, name, address, city, country
├── star_rating (1.0 – 5.0)
├── description, is_active
└── room_types[]

RoomType
├── id, hotel_id, name
├── capacity, bed_type
├── price_per_night, total_rooms
└── bookings[]

Booking
├── id, user_id, room_type_id
├── check_in, check_out, guests_count
├── total_price
├── status: pending → confirmed → completed | cancelled
├── cancelled_at, cancellation_reason
└── payment?

Payment
├── id, booking_id
├── amount, currency (RUB)
├── status: pending → succeeded | cancelled | refunded
└── provider_tx_id (YooKassa ID)

RefreshToken
├── id, user_id, token_hash
├── expires_at, revoked_at
```

---

## API эндпоинты

Все маршруты доступны с префиксом `/api/v1`. Интерактивная документация: `http://localhost/docs`

### Auth `/api/v1/auth`

| Метод | Путь | Описание |
|---|---|---|
| POST | `/register` | Регистрация нового пользователя |
| POST | `/login` | Вход (возвращает access + refresh токены) |
| POST | `/refresh` | Обновление пары токенов |
| POST | `/logout` | Выход (отзыв refresh-токена) |

### Hotels `/api/v1/hotels`

| Метод | Путь | Описание |
|---|---|---|
| GET | `/` | Список отелей с фильтрацией (город, страна, звёздность) |
| GET | `/{hotel_id}` | Детальная информация об отеле |
| GET | `/{hotel_id}/room-types` | Типы номеров отеля |
| GET | `/{hotel_id}/room-types/{room_type_id}/availability` | Доступность номера на даты |

### Bookings `/api/v1/bookings` (требует авторизации)

| Метод | Путь | Описание |
|---|---|---|
| POST | `/` | Создать бронирование |
| GET | `/` | Мои бронирования (с фильтрацией по статусу) |
| GET | `/{booking_id}` | Конкретное бронирование |
| POST | `/{booking_id}/cancel` | Отменить бронирование |

### Payments `/api/v1/payments` (требует авторизации)

| Метод | Путь | Описание |
|---|---|---|
| POST | `/checkout/{booking_id}` | Инициировать оплату (возвращает URL ЮКассы) |
| GET | `/{booking_id}` | Информация о платеже |
| POST | `/webhook` | Webhook от ЮКассы |

### Users `/api/v1/users` (требует авторизации)

| Метод | Путь | Описание |
|---|---|---|
| GET | `/me` | Профиль текущего пользователя |
| PATCH | `/me` | Обновить профиль |
| DELETE | `/me` | Удалить аккаунт |
| POST | `/me/change-password` | Сменить пароль |

### Admin `/api/v1/admin` (требует роль admin)

| Метод | Путь | Описание |
|---|---|---|
| POST | `/hotels` | Создать отель |
| PATCH | `/hotels/{hotel_id}` | Обновить данные отеля |
| DELETE | `/hotels/{hotel_id}` | Скрыть отель |
| POST | `/hotels/{hotel_id}/room-types` | Добавить тип номера |
| PATCH | `/hotels/{hotel_id}/room-types/{room_type_id}` | Обновить тип номера |
| GET | `/bookings` | Все бронирования (pagination) |
| PATCH | `/bookings/{booking_id}/cancel` | Отменить бронирование |

### Health

| Метод | Путь | Описание |
|---|---|---|
| GET | `/health` | Проверка состояния сервиса |

---

## Фоновые задачи

Celery Beat запускает периодические задачи по расписанию:

| Задача | Расписание | Описание |
|---|---|---|
| `cancel_pending_bookings` | каждые N минут (TTL_PENDING_BOOKINGS) | Отменяет неоплаченные бронирования с отменой платежа в ЮКассе |
| `complete_finished_bookings` | каждый день в 00:00 | Переводит подтверждённые бронирования с прошедшей датой выезда в статус `completed` |
| `clean_refresh_tokens` | каждый день в 01:00 | Удаляет истёкшие и отозванные refresh-токены |
| `send_checkin_reminders` | каждый день в 10:00 | Отправляет email-напоминания пользователям, заезд которых через 24–48 часов |

---

## Безопасность

- **Пароли** хэшируются через bcrypt
- **Refresh-токены** хранятся в виде SHA-256 хэша, не в открытом виде
- **Rate limiting** на всех эндпоинтах через slowapi (хранилище - Redis)
- **Correlation ID** middleware: каждый запрос получает уникальный `X-Request-ID` для трассировки в логах
- **Webhook IP verification**: опциональная проверка IP-адресов ЮКассы
- **Row-level locking** (`SELECT FOR UPDATE`) при создании и отмене бронирований

---

## Тестирование

Проект содержит **211 тестов** в трёх уровнях:

```
tests/
├── unit/               # юнит-тесты
│   ├── test_schemas.py     # Pydantic валидация
│   ├── test_security.py    # хэширование, JWT
│   └── test_utils.py       # вспомогательные функции
├── integration/        # интеграционные тесты (реальная тестовая БД)
│   ├── test_auth_service.py
│   ├── test_booking_service.py
│   └── test_hotel_service.py
└── e2e/                # сквозные тесты (через HTTP-клиент)
    ├── test_auth.py
    ├── test_hotels.py
    ├── test_bookings.py
    ├── test_payments.py
    ├── test_users.py
    └── test_admin.py
```

Запуск тестов:

```bash
pytest
```

---

## Быстрый старт

### Предварительные требования

- Docker и Docker Compose

### 1. Клонировать репозиторий

```bash
git clone <repo_url>
cd booking_service_project
```

### 2. Настроить переменные окружения

```bash
cp .env.example .env
# Заполнить .env своими значениями
```

### 3. Запустить проект

```bash
make start
```

Или напрямую:

```bash
sudo docker compose up -d --build
```

Сервис поднимет:
- **PostgreSQL** - хранилище данных
- **Redis** - кэш, rate limiting, брокер задач
- **FastAPI** - основное приложение (порт 8000 внутри контейнера)
- **Celery Worker** - выполнение фоновых задач
- **Celery Beat** - планировщик периодических задач
- **Nginx** - обратный прокси на порту **80**
- **ngrok** - туннель для разработки (для тестирования webhook-ов ЮКассы)

Миграции применяются автоматически при старте приложения.

### Полезные команды

```bash
make stop      # остановить контейнеры
make restart   # перезапустить
make check     # проверить статус контейнеров
make logs      # посмотреть логи
make delete    # остановить и удалить тома (включая БД)
```

---

## Переменные окружения

```env
# База данных
DB_URL=postgresql+asyncpg://user:password@database:5432/booking_service
POSTGRES_USER=admin
POSTGRES_DB=booking_service
POSTGRES_PASSWORD=secret

# JWT
SECRET_KEY=your_secret_key
EXPIRE_ACCESS_TOKEN_MIN=15
EXPIRE_REFRESH_TOKEN_DAYS=30
MAX_ACTIVE_SESSIONS=5
ALGORITHM=HS256

# ЮКасса
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key
RETURN_URL=https://your-domain.com/payment/result
VERIFY_WEBHOOK_IP=false

# Redis
RATE_LIMITING_STORAGE=redis://redis:6379/0
CACHE_STORAGE=redis://redis:6379/1
TASKS_STORAGE=redis://redis:6379/2

# Email
MAIL_SERVER=smtp.example.com
MAIL_PORT=587
MAIL_USERNAME=user@example.com
MAIL_PASSWORD=mail_password
MAIL_FROM=noreply@example.com

# Бронирования
TTL_PENDING_BOOKINGS=10    # минут до автоотмены неоплаченного

# Прочее
LOG_LEVEL=INFO
NGROK_AUTHTOKEN=           # только для разработки
```
