# Booking Service

An asynchronous REST API hotel booking service built with FastAPI. Covers the full cycle - from searching for a hotel and booking a room to online payment via YooKassa.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Features](#features)
- [Data Models](#data-models)
- [API Endpoints](#api-endpoints)
- [Background Tasks](#background-tasks)
- [Security](#security)
- [Testing](#testing)
- [Quick Start](#quick-start)
- [Environment Variables](#environment-variables)

---

## Tech Stack

| Layer | Tool |
|---|---|
| Framework | FastAPI 0.136, Python 3.12 |
| Database | PostgreSQL 15 + SQLAlchemy 2.0 (async) + asyncpg |
| Migrations | Alembic |
| Caching | Redis + fastapi-cache2 |
| Task queue | Celery + Celery Beat + Redis |
| Auth | JWT (access + refresh tokens), bcrypt, python-jose |
| Payments | YooKassa SDK |
| Rate limiting | slowapi (Redis storage) |
| Validation | Pydantic v2 |
| Logging | Structured logs + Correlation ID middleware |
| Reverse proxy | Nginx |
| Containerization | Docker + Docker Compose |
| Tests | pytest + pytest-asyncio |

---

## Architecture

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
          │  (main data)  │  │  cache/limits │
          │               │  │  / tasks      │
          └───────────────┘  └───────┬───────┘
                                     │
                       ┌─────────────▼───────────────┐
                       │  Celery Worker + Beat       │
                       │  (scheduled background jobs)│
                       └─────────────────────────────┘
```

The application follows a layered architecture:

- **routers/** - HTTP handlers, request validation
- **services/** - business logic, database queries
- **schemas/** - Pydantic request/response schemas
- **database/models.py** - SQLAlchemy ORM models
- **celery_app.py** - periodic background tasks

---

## Features

### Authentication
- Registration and login via email/password
- Token pair: short-lived access token (JWT) + long-lived refresh token
- Refresh token rotation on every renewal
- Token revocation on logout and password change
- Active session limit per user

### Hotels and Rooms
- Hotel search with filters (city, country, star rating)
- Detailed hotel information
- Room type listing with characteristics
- Room availability check for specific dates

### Bookings
- Booking creation with automatic total price calculation
- Double-booking protection via `SELECT ... FOR UPDATE`
- View own bookings filtered by status
- Booking cancellation with a reason
- Automatic cancellation of unpaid bookings

### Payments (YooKassa)
- Create a payment session and receive a redirect URL
- Webhook notification handling from YooKassa
- Automatic booking status update on successful payment
- Payment cancellation when booking is cancelled

### Admin Panel
- Create, update, and hide hotels
- Manage room types
- View all bookings with pagination
- Cancel any booking

### User Profile
- View and update profile
- Change password (revokes all tokens automatically)
- Delete account

---

## Data Models

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

## API Endpoints

All routes are available under the `/api/v1` prefix. Interactive docs: `http://localhost/docs`

### Auth `/api/v1/auth`

| Method | Path | Description |
|---|---|---|
| POST | `/register` | Register a new user |
| POST | `/login` | Log in (returns access + refresh tokens) |
| POST | `/refresh` | Refresh the token pair |
| POST | `/logout` | Log out (revokes refresh token) |

### Hotels `/api/v1/hotels`

| Method | Path | Description |
|---|---|---|
| GET | `/` | Hotel list with filtering (city, country, stars) |
| GET | `/{hotel_id}` | Hotel details |
| GET | `/{hotel_id}/room-types` | Hotel room types |
| GET | `/{hotel_id}/room-types/{room_type_id}/availability` | Room availability for dates |

### Bookings `/api/v1/bookings` (auth required)

| Method | Path | Description |
|---|---|---|
| POST | `/` | Create a booking |
| GET | `/` | My bookings (filterable by status) |
| GET | `/{booking_id}` | Specific booking |
| POST | `/{booking_id}/cancel` | Cancel a booking |

### Payments `/api/v1/payments` (auth required)

| Method | Path | Description |
|---|---|---|
| POST | `/checkout/{booking_id}` | Initiate payment (returns YooKassa URL) |
| GET | `/{booking_id}` | Payment info |
| POST | `/webhook` | YooKassa webhook receiver |

### Users `/api/v1/users` (auth required)

| Method | Path | Description |
|---|---|---|
| GET | `/me` | Current user profile |
| PATCH | `/me` | Update profile |
| DELETE | `/me` | Delete account |
| POST | `/me/change-password` | Change password |

### Admin `/api/v1/admin` (admin role required)

| Method | Path | Description |
|---|---|---|
| POST | `/hotels` | Create hotel |
| PATCH | `/hotels/{hotel_id}` | Update hotel |
| DELETE | `/hotels/{hotel_id}` | Hide hotel |
| POST | `/hotels/{hotel_id}/room-types` | Add room type |
| PATCH | `/hotels/{hotel_id}/room-types/{room_type_id}` | Update room type |
| GET | `/bookings` | All bookings (paginated) |
| PATCH | `/bookings/{booking_id}/cancel` | Cancel any booking |

### Health

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Service health check |

---

## Background Tasks

Celery Beat schedules periodic background tasks:

| Task | Schedule | Description |
|---|---|---|
| `cancel_pending_bookings` | every N minutes (TTL_PENDING_BOOKINGS) | Cancels overdue unpaid bookings and cancels YooKassa payments |
| `complete_finished_bookings` | daily at 00:00 | Marks confirmed bookings past check-out date as `completed` |
| `clean_refresh_tokens` | daily at 01:00 | Removes expired and revoked refresh tokens |
| `send_checkin_reminders` | daily at 10:00 | Sends email reminders to users checking in within 24–48 hours |

---

## Security

- **Passwords** are hashed using bcrypt
- **Refresh tokens** stored as SHA-256 hashes, never in plaintext
- **Rate limiting** on all endpoints via slowapi (Redis backend)
- **Correlation ID** middleware: every request gets a unique `X-Request-ID` for log tracing
- **Webhook IP verification**: optional check against YooKassa IP ranges
- **Row-level locking** (`SELECT FOR UPDATE`) when creating and cancelling bookings

---

## Testing

The project contains **211 tests** across three levels:

```
tests/
├── unit/               # unit tests
│   ├── test_schemas.py     # Pydantic validation
│   ├── test_security.py    # hashing, JWT
│   └── test_utils.py       # helper functions
├── integration/        # integration tests (real test database)
│   ├── test_auth_service.py
│   ├── test_booking_service.py
│   └── test_hotel_service.py
└── e2e/                # end-to-end tests (via HTTP client)
    ├── test_auth.py
    ├── test_hotels.py
    ├── test_bookings.py
    ├── test_payments.py
    ├── test_users.py
    └── test_admin.py
```

Run tests:

```bash
pytest
```

---

## Quick Start

### Prerequisites

- Docker and Docker Compose

### 1. Clone the repository

```bash
git clone <repo_url>
cd booking_service_project
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Fill in .env with your values
```

### 3. Start the project

```bash
make start
```

Or directly:

```bash
sudo docker compose up -d --build
```

This starts:
- **PostgreSQL** - main data store
- **Redis** - cache, rate limiting, task broker
- **FastAPI** - main application (port 8000 inside container)
- **Celery Worker** - background task executor
- **Celery Beat** - periodic task scheduler
- **Nginx** - reverse proxy on port **80**
- **ngrok** - development tunnel (for YooKassa webhook testing)

Database migrations are applied automatically on application startup.

### Useful Commands

```bash
make stop      # stop containers
make restart   # restart
make check     # check container status
make logs      # view logs
make delete    # stop and remove volumes (including the database)
```

---

## Environment Variables

```env
# Database
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

# YooKassa
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

# Bookings
TTL_PENDING_BOOKINGS=10    # minutes until unpaid booking is auto-cancelled

# Misc
LOG_LEVEL=INFO
NGROK_AUTHTOKEN=           # development only
```
