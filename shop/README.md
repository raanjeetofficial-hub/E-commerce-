# Parcel — FastAPI + PostgreSQL e-commerce

## Run with Docker (easiest)
    docker compose up --build
Open http://localhost:8000  (API docs: http://localhost:8000/docs)

## Run locally
    # 1. start Postgres and create a database called "shop"
    cd backend && pip install -r requirements.txt
    export DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/shop
    uvicorn app.main:app --reload

## Accounts
- Admin: admin@shop.com / admin123 (change via ADMIN_EMAIL / ADMIN_PASSWORD; set SECRET_KEY in production)
- Customers sign up from the site. Sign-up always creates a `customer`.

## Who can do what
| Role | Abilities |
|---|---|
| Visitor | Browse/search products, fill a cart |
| Customer | Everything above + place orders, view own order history |
| Admin | Full CRUD on products, orders (status/delete; cancel restocks), users (role/delete) |

Admin endpoints live under `/api/admin/*` and are protected server-side by `require_admin`, not just hidden in the UI.
Checkout locks product rows (`SELECT ... FOR UPDATE`) so stock can't be oversold. Payments are simulated; plug in Stripe in `place_order`.
