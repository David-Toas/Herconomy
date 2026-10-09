# Subscription-Based Marketplace & Payment Platform

[![Tests](https://img.shields.io/badge/Tests-24%20Passed%20(100%25)-brightgreen.svg)]()
[![Django](https://img.shields.io/badge/Django-5.1-blue.svg)]()
[![DRF](https://img.shields.io/badge/DRF-3.15-red.svg)]()
[![Celery](https://img.shields.io/badge/Celery-5.6-green.svg)]()
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)]()
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)]()

Production-quality backend for a subscription-based marketplace where customers purchase subscription plans from service providers. Handles payments, webhooks, subscription expiry, asynchronous background processing, strict role-based access control, concurrency defense, and idempotent operations.

---

## Table of Contents
1. [Key Architecture & Design Highlights](#key-architecture--design-highlights)
2. [Tech Stack](#tech-stack)
3. [Quick Start with Docker Compose](#quick-start-with-docker-compose)
4. [Local Setup (Without Docker)](#local-setup-without-docker)
5. [Environment Variables](#environment-variables)
6. [Running Automated Tests](#running-automated-tests)
7. [API Documentation & Interactive Swagger](#api-documentation--interactive-swagger)
8. [Concurrency, Idempotency & Data Integrity Architecture](#concurrency-idempotency--data-integrity-architecture)
9. [Celery Background Processing & Celery Beat](#celery-background-processing--celery-beat)
10. [Caching & Invalidation Strategy](#caching--invalidation-strategy)
11. [Database Indexing & Query Optimization](#database-indexing--query-optimization)
12. [Django Admin Configuration](#django-admin-configuration)
13. [Assumptions & Engineering Trade-offs](#assumptions--engineering-trade-offs)

---

## Key Architecture & Design Highlights

* **Defense-in-Depth Concurrency**: Combines PostgreSQL partial unique constraints (`UniqueConstraint` with conditional `Q` objects) and pessimistic row-level locking (`select_for_update`) within `transaction.atomic()` boundaries.
* **Strict Webhook Idempotency**: Payment webhooks enforce atomic row locking and state transitions. Re-delivered webhooks return HTTP 200 immediately without re-calculating dates or triggering duplicate side-effects.
* **Safe Asynchronous Dispatching**: All background tasks (e.g. simulated customer receipt emails) are strictly dispatched via `transaction.on_commit()`, preventing phantom tasks if a transaction rolls back.
* **Service Layer Pattern**: Business logic is decoupled into dedicated service modules (`apps/subscriptions/services.py`, `apps/payments/services.py`, `apps/plans/services.py`) rather than fat models or bloated views.
* **High-Performance Querying**: Subscription and plan queries leverage `select_related()` joins and composite database indexes, eliminating N+1 queries.
* **Atomic Cache Invalidation**: Public plans are cached in Redis and invalidated via version bumping whenever a provider creates, modifies, or deletes a plan.

---

## Tech Stack

* **Framework**: Django 5.1, Django REST Framework 3.15
* **Authentication**: `djangorestframework-simplejwt` (JWT Auth)
* **Database**: PostgreSQL 16 (production/Docker) / SQLite (local fallback)
* **Task Queue & Scheduler**: Celery 5.6 + Redis 7 + `django-celery-beat`
* **Caching**: Redis Cache (`django.core.cache.backends.redis.RedisCache`)
* **API Documentation**: OpenAPI 3.0 via `drf-spectacular` (Swagger UI & Redoc)
* **Containerization**: Docker & Docker Compose

---

## Quick Start with Docker Compose

To start the complete infrastructure (PostgreSQL, Redis, Django Web, Celery Worker, Celery Beat):

```bash
# 1. Clone repository
git clone <repository_url>
cd subscription_marketplace

# 2. Copy environment file
cp .env.example .env

# 3. Build and launch containers
docker compose up --build
```

The services will start on:
* **Django REST API**: `http://localhost:8000/api/`
* **Swagger UI Documentation**: `http://localhost:8000/api/docs/`
* **Redoc UI**: `http://localhost:8000/api/redoc/`
* **Django Admin**: `http://localhost:8000/admin/`

To create a superuser inside the container:
```bash
docker compose exec web python manage.py createsuperuser
```

---

## Local Setup (Without Docker)

If running directly on a machine with Python installed:

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env

# 4. Apply database migrations
python manage.py migrate

# 5. Run development server
python manage.py runserver
```

*(Optional) Start Celery worker and beat in separate terminals:*
```bash
celery -A config worker --loglevel=info
celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

---

## Environment Variables

| Variable | Description | Default (Local / Docker) |
| :--- | :--- | :--- |
| `SECRET_KEY` | Django secret key | Pre-configured in `.env.example` |
| `DEBUG` | Enable debug mode | `True` |
| `ALLOWED_HOSTS` | Comma-separated list of hosts | `localhost,127.0.0.1,web` |
| `DATABASE_URL` | Database connection string | `postgres://postgres:postgrespassword@db:5432/subscription_db` |
| `REDIS_URL` | Redis URL for caching | `redis://redis:6379/0` |
| `CELERY_BROKER_URL` | Celery broker URL | `redis://redis:6379/1` |
| `CELERY_RESULT_BACKEND` | Celery result backend URL | `redis://redis:6379/2` |
| `WEBHOOK_SECRET` | Secret key for webhook signature validation | `test_webhook_secret_key_12345` |

---

## Running Automated Tests

The test suite covers authentication, role permissions, plan CRUD, caching, subscription lifecycle, webhook idempotency, background tasks, and multi-threaded concurrency.

Run tests via Docker:
```bash
docker compose exec web python manage.py test
```

Or run locally:
```bash
python manage.py test
```

### Test Coverage Highlights:
1. `tests/test_auth.py`: Registration, duplicate email rejection, JWT login, and role privilege escalation prevention (`role` field is read-only).
2. `tests/test_plans.py`: Provider plan creation, customer permission restriction (403 Forbidden), cross-provider plan modification prevention, and cache invalidation.
3. `tests/test_subscriptions.py`: Subscription creation in `PENDING` status, inactive plan subscription prevention, duplicate active subscription rejection (409 Conflict), cancellation, and periodic expiry task.
4. `tests/test_payments.py`: Webhook success, subscription activation, date calculation, async email dispatch, webhook failure, invalid reference (404), amount mismatch (400), and **webhook idempotency** (duplicate webhook produces no side-effects).
5. `tests/test_concurrency.py`: `ThreadPoolExecutor` tests simulating two concurrent threads competing for the same subscription and the same payment webhook simultaneously.

---

## API Documentation & Interactive Swagger

Interactive API documentation is powered by **drf-spectacular**:
* **Swagger UI**: [http://localhost:8000/api/docs/](http://localhost:8000/api/docs/)
* **ReDoc**: [http://localhost:8000/api/redoc/](http://localhost:8000/api/redoc/)
* **Raw Schema**: [http://localhost:8000/api/schema/](http://localhost:8000/api/schema/)

### Core Endpoint Summary

#### 1. Authentication (`/api/auth/`)
* `POST /api/auth/register/`: Registers a Customer or Provider user; returns JWT credentials.
* `POST /api/auth/login/`: Validates email and password; returns access & refresh tokens.
* `GET  /api/auth/me/`: Retrieves current profile.
* `PATCH /api/auth/me/`: Updates personal details. **Note**: The `role` field is strictly read-only.

#### 2. Subscription Plans (`/api/plans/`)
* `POST /api/plans/`: Create a plan (`IsProvider` only).
* `GET  /api/plans/`: Public list of active plans (cached in Redis).
* `GET  /api/plans/{id}/`: Retrieve plan details.
* `PATCH /api/plans/{id}/`: Update plan (only owning provider).
* `DELETE /api/plans/{id}/`: Delete/deactivate plan (only owning provider).

#### 3. Subscriptions (`/api/subscriptions/`)
* `POST /api/subscriptions/`: Customer initiates subscription to a plan.
  * Body: `{"plan_id": 15}`
  * Response:
    ```json
    {
      "subscription_id": 31,
      "payment_reference": "PAY-8F92A1B7C3D4",
      "status": "PENDING",
      "amount": "49.99",
      "currency": "USD"
    }
    ```
* `GET  /api/subscriptions/`: List user's subscriptions (paginated, supports `?status=ACTIVE`).
* `GET  /api/subscriptions/{id}/`: Retrieve specific subscription.
* `POST /api/subscriptions/{id}/cancel/`: Cancel subscription.

#### 4. Payments & Webhooks (`/api/payments/`)
* `POST /api/payments/webhook/`: External payment gateway notification.
  * Headers (optional): `X-Webhook-Signature: <hmac_sha256>`
  * Body:
    ```json
    {
      "event": "payment.success",
      "reference": "PAY-8F92A1B7C3D4",
      "provider_reference": "STRIPE-ch_3N1abc",
      "amount": "49.99"
    }
    ```
  * Response:
    ```json
    {
      "status": "processed",
      "message": "Payment succeeded and subscription activated.",
      "reference": "PAY-8F92A1B7C3D4"
    }
    ```

---

## Concurrency, Idempotency & Data Integrity Architecture

### 1. Two Simultaneous Subscription Requests
* **Problem**: A customer clicks "Subscribe" twice in rapid succession. If checking `if not Subscription.objects.filter(...).exists():` in Python, both requests might pass before either commits, creating duplicate active subscriptions.
* **Solution**:
  1. Wrapped in `transaction.atomic()`.
  2. The Plan row is locked using `Plan.objects.select_for_update().get(id=plan_id)` to ensure plan active status cannot change mid-flight.
  3. **PostgreSQL Partial Unique Constraint**:
     ```python
     models.UniqueConstraint(
         fields=['customer', 'plan'],
         condition=models.Q(status__in=['ACTIVE', 'PENDING']),
         name='unique_active_or_pending_sub_per_customer_plan'
     )
     ```
     Even if two threads reach the database simultaneously, the database guarantees that exactly one commits and the second raises `IntegrityError`. The application intercepts this and returns HTTP `409 Conflict`.

### 2. Payment Webhook Idempotency & Concurrency
* **Problem**: Payment gateways (Stripe, Paystack) frequently deliver webhooks multiple times due to network timeouts. Two parallel Celery workers or web requests could attempt to process the same reference at the same time.
* **Solution**:
  1. `with transaction.atomic():`
  2. The Payment record is row-locked using `Payment.objects.select_for_update().get(reference=reference)`.
  3. **State Machine Idempotency Check**:
     ```python
     if payment.status == PaymentStatus.SUCCESS:
         return {"status": "already_processed"}
     ```
     If the payment is already confirmed, the second request immediately exits with HTTP 200 without recalculating dates or queueing duplicate background jobs.
  4. **Amount Verification**: The incoming webhook `amount` must match `payment.amount` down to the cent, preventing underpayment fraud.

### 3. Safe Asynchronous Task Enqueueing (`transaction.on_commit`)
* **Problem**: Calling `.delay()` inside a database transaction can trigger a race condition where the Celery worker runs before the database transaction has committed, causing `Payment.DoesNotExist` or duplicate execution. If the transaction rolls back, a phantom email would still be sent.
* **Solution**:
  ```python
  transaction.on_commit(
      lambda: send_payment_notification_email.delay(payment.id)
  )
  ```
  The Celery task is only dispatched **after** the transaction is committed to the database.

---

## Celery Background Processing & Celery Beat

1. **Subscription Expiry Periodic Task (`apps/subscriptions/tasks.py`)**:
   * Scheduled via Celery Beat every 60 seconds (`check_and_expire_subscriptions`).
   * Queries `Subscription.objects.filter(status='ACTIVE', end_date__lte=timezone.now())`.
   * Performs an efficient bulk `.update(status='EXPIRED')`, minimizing memory overhead.

2. **Simulated Payment Notification Task (`apps/payments/tasks.py`)**:
   * Task `send_payment_notification_email(payment_id)` executes asynchronously.
   * Emulates email dispatch with exponential retry backoff (`max_retries=3, default_retry_delay=10`).
   * Logs execution:
     `[EMAIL DISPATCH] Successfully simulated email to customer@example.com for Payment Ref: PAY-...`

---

## Caching & Invalidation Strategy

* **Cache Layer**: Redis Cache backend (`django.core.cache.backends.redis.RedisCache`) with a 15-minute TTL.
* **Cached Endpoint**: Public plan listings (`GET /api/plans/`).
* **Cache Keys**: Versioned keys formatted as `public_plans:v{version}:page_{page}:size_{size}`.
* **Invalidation Strategy**:
  When a provider creates, updates, or deletes a plan:
  1. `apps/plans/services.py` atomically increments the cache version (`cache.incr('plans_cache_version')`).
  2. Deletes Redis pattern matching `*public_plans:*`.
  3. Any subsequent GET request instantly fetches fresh data from PostgreSQL and warms the cache.

---

## Database Indexing & Query Optimization

### 1. Avoiding N+1 Queries
* In `SubscriptionViewSet.get_queryset()`:
  ```python
  Subscription.objects.select_related('customer', 'plan', 'plan__provider')
  ```
  Reduces what would normally be 3 queries per subscription item into a single SQL query with joins.
* In `PlanViewSet.get_queryset()`:
  ```python
  Plan.objects.select_related('provider')
  ```

### 2. Composite Database Indexes
To maintain sub-millisecond query performance at scale, composite indexes are placed across foreign keys and query filters:
* `subscriptions_customer_status_idx`: `['customer', 'status']` — accelerates customer subscription filtering.
* `subscriptions_status_end_date_idx`: `['status', 'end_date']` — optimizes periodic Celery expiry queries.
* `plans_is_active_created_at_idx`: `['is_active', 'created_at']` — speeds up public catalog listing.
* `payments_reference_idx`: Unique index on `reference` — guarantees fast lookups during webhook processing.

---

## Django Admin Configuration

Configured under `/admin/`:
* **Users & Providers**: List display, role filter, email search, date filters.
* **Plans**: Filter by `billing_interval`, `is_active`, created date; search by provider email and name.
* **Subscriptions**: Filter by `status`, `created_at`, `end_date`; search by customer email and plan name.
* **Payments**: Filter by `status`, `currency`, `created_at`; search by payment reference and provider reference.

---

## Assumptions & Engineering Trade-offs

1. **Simulated Payment Provider**: As instructed, payments initiate in `PENDING` status with an internally generated reference (`PAY-<UUID>`). A webhook simulating an external provider (e.g. Stripe/Paystack) updates payment status to `SUCCESS` and activates the subscription.
2. **Partial Database Constraints over Application Validation**: In distributed systems, relying solely on `serializer.validate()` or `if existing.exists()` fails under concurrent requests. We enforce integrity via PostgreSQL partial unique constraints.
3. **Database Fallback for Local Dev**: Settings automatically connect to PostgreSQL when `DATABASE_URL` is configured (default in Docker), while providing a fallback to SQLite for local runs where PostgreSQL is not locally installed.
4. **Webhook Security**: Includes bonus HMAC-SHA256 signature verification via the `X-Webhook-Signature` header. When testing without this header, the endpoint falls back gracefully.
