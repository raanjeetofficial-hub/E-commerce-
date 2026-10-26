import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func
from .database import Base, engine, SessionLocal
from .models import User, Product
from .routes import public, admin, UPLOAD_DIR
from .security import hash_password

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"

# name, description, price, stock, category, image keywords
SAMPLE = [
    ("Ceramic pour-over set", "Dripper, carafe and two cups in matte stoneware.", 48.00, 25, "Kitchen", "coffee,pourover"),
    ("Linen apron", "Heavyweight washed linen with adjustable neck strap.", 32.50, 40, "Kitchen", "apron,kitchen"),
    ("Walnut desk tray", "Hand-finished tray for pens, cables and keys.", 27.00, 60, "Home office", "desk,organizer"),
    ("Mechanical keyboard", "75% layout, hot-swappable switches, USB-C.", 119.00, 15, "Home office", "mechanical,keyboard"),
    ("Merino beanie", "Soft ribbed knit in six colours.", 24.00, 80, "Apparel", "beanie,hat"),
    ("Canvas tote bag", "Thick cotton canvas with an inner zip pocket.", 19.99, 100, "Apparel", "tote,bag"),
    ("Trail water bottle", "750 ml insulated steel, keeps cold for 24 hours.", 29.00, 50, "Outdoor", "water,bottle"),
    ("Pocket headlamp", "300 lumens, rechargeable, weighs 45 g.", 22.00, 35, "Outdoor", "headlamp,camping"),
]


def img(i, kw):
    return f"https://loremflickr.com/600/450/{kw}?lock={i}"


def seed():
    with SessionLocal() as db:
        email = os.getenv("ADMIN_EMAIL", "admin@shop.com").lower()
        if not db.scalar(select(User).where(User.email == email)):
            db.add(User(email=email, full_name="Store Admin", role="admin",
                        hashed_password=hash_password(os.getenv("ADMIN_PASSWORD", "admin123"))))
        if db.scalar(select(func.count(Product.id))) == 0:
            db.add_all(Product(name=n, description=d, price=p, stock=st, category=c, image_url=img(i, kw))
                       for i, (n, d, p, st, c, kw) in enumerate(SAMPLE, 1))
        db.commit()
        # give existing sample products an image if they don't have one yet
        for i, (n, *_, kw) in enumerate(SAMPLE, 1):
            p = db.scalar(select(Product).where(Product.name == n))
            if p and not p.image_url:
                p.image_url = img(i, kw)
        db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    seed()
    yield


app = FastAPI(title="ShopFast", lifespan=lifespan)
app.include_router(public)
app.include_router(admin)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
