import os
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session
from . import schemas as s
from .database import get_db
from .models import User, Product, Order, OrderItem
from .security import (hash_password, verify_password, create_token,
                       get_current_user, require_admin)

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", Path(__file__).resolve().parents[1] / "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}

# ---------------------------------------------------------------- public / customer
public = APIRouter(prefix="/api")


@public.post("/auth/register", response_model=s.UserOut, status_code=201)
def register(data: s.RegisterIn, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(400, "Email already registered")
    user = User(email=email, full_name=data.full_name,
                hashed_password=hash_password(data.password), role="customer")
    db.add(user); db.commit(); db.refresh(user)
    return user


@public.post("/auth/login", response_model=s.Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(401, "Wrong email or password")
    return s.Token(access_token=create_token(user.id))


@public.get("/auth/me", response_model=s.UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@public.get("/products", response_model=list[s.ProductOut])
def list_products(q: str = "", category: str = "", db: Session = Depends(get_db)):
    stmt = select(Product).where(Product.is_active.is_(True))
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    if category:
        stmt = stmt.where(Product.category == category)
    return db.scalars(stmt.order_by(Product.id.desc())).all()


@public.get("/products/{pid}", response_model=s.ProductOut)
def get_product(pid: int, db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p or not p.is_active:
        raise HTTPException(404, "Product not found")
    return p


@public.post("/orders", response_model=s.OrderOut, status_code=201)
def place_order(data: s.OrderIn, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    qty: dict[int, int] = {}
    for i in data.items:
        qty[i.product_id] = qty.get(i.product_id, 0) + i.quantity
    # lock rows so two buyers can't oversell the same stock
    products = {p.id: p for p in db.scalars(
        select(Product).where(Product.id.in_(qty)).order_by(Product.id).with_for_update())}
    order = Order(user_id=user.id, address=data.address, total=Decimal(0))
    total = Decimal(0)
    for pid, q in qty.items():
        p = products.get(pid)
        if not p or not p.is_active:
            raise HTTPException(400, f"Product {pid} is no longer available")
        if p.stock < q:
            raise HTTPException(400, f"Only {p.stock} left of {p.name}")
        p.stock -= q
        total += p.price * q
        order.items.append(OrderItem(product_id=pid, name=p.name, price=p.price, quantity=q))
    order.total = total
    db.add(order); db.commit(); db.refresh(order)
    return order


@public.get("/orders/mine", response_model=list[s.OrderOut])
def my_orders(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.scalars(select(Order).where(Order.user_id == user.id)
                      .order_by(Order.id.desc())).all()


# ---------------------------------------------------------------- admin (full CRUD)
admin = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])


@admin.post("/upload")
async def a_upload_image(file: UploadFile = File(...)):
    ext = IMAGE_TYPES.get(file.content_type)
    if not ext:
        raise HTTPException(400, "Only JPG, PNG, WEBP or GIF images are allowed")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(400, "Image must be under 5 MB")
    name = f"{uuid4().hex}{ext}"
    (UPLOAD_DIR / name).write_bytes(data)
    return {"url": f"/uploads/{name}"}


@admin.get("/products", response_model=list[s.ProductOut])
def a_list_products(db: Session = Depends(get_db)):
    return db.scalars(select(Product).order_by(Product.id.desc())).all()


@admin.post("/products", response_model=s.ProductOut, status_code=201)
def a_create_product(data: s.ProductIn, db: Session = Depends(get_db)):
    p = Product(**data.model_dump())
    db.add(p); db.commit(); db.refresh(p)
    return p


@admin.put("/products/{pid}", response_model=s.ProductOut)
def a_update_product(pid: int, data: s.ProductIn, db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found")
    for k, v in data.model_dump().items():
        setattr(p, k, v)
    db.commit(); db.refresh(p)
    return p


@admin.delete("/products/{pid}", status_code=204)
def a_delete_product(pid: int, db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found")
    db.delete(p); db.commit()
    return Response(status_code=204)


@admin.get("/orders", response_model=list[s.OrderOut])
def a_list_orders(db: Session = Depends(get_db)):
    return db.scalars(select(Order).order_by(Order.id.desc())).all()


@admin.put("/orders/{oid}/status", response_model=s.OrderOut)
def a_set_status(oid: int, data: s.StatusIn, db: Session = Depends(get_db)):
    o = db.get(Order, oid)
    if not o:
        raise HTTPException(404, "Order not found")
    if data.status == "cancelled" and o.status != "cancelled":  # put stock back
        for it in o.items:
            if it.product_id and (p := db.get(Product, it.product_id)):
                p.stock += it.quantity
    o.status = data.status
    db.commit(); db.refresh(o)
    return o


@admin.delete("/orders/{oid}", status_code=204)
def a_delete_order(oid: int, db: Session = Depends(get_db)):
    o = db.get(Order, oid)
    if not o:
        raise HTTPException(404, "Order not found")
    db.delete(o); db.commit()
    return Response(status_code=204)


@admin.get("/users", response_model=list[s.UserOut])
def a_list_users(db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.id)).all()


@admin.put("/users/{uid}/role", response_model=s.UserOut)
def a_set_role(uid: int, data: s.RoleIn, db: Session = Depends(get_db),
               me: User = Depends(require_admin)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == me.id:
        raise HTTPException(400, "You can't change your own role")
    u.role = data.role
    db.commit(); db.refresh(u)
    return u


@admin.delete("/users/{uid}", status_code=204)
def a_delete_user(uid: int, db: Session = Depends(get_db),
                  me: User = Depends(require_admin)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == me.id:
        raise HTTPException(400, "You can't delete yourself")
    db.delete(u); db.commit()
    return Response(status_code=204)
