from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import uuid
import bcrypt
import jwt
from contextlib import asynccontextmanager
import sqlite3
import json

# ============================================
# CONFIGURATION
# ============================================

SECRET_KEY = "your-super-secret-key-change-this-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
DATABASE_URL = "lako.db"

# ============================================
# DATABASE SETUP
# ============================================

def init_db():
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            hashed_password TEXT NOT NULL,
            role TEXT NOT NULL,
            is_verified INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            eula_accepted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Customers table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            user_id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            avatar_url TEXT,
            default_location_lat REAL,
            default_location_lng REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Vendors table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vendors (
            user_id TEXT PRIMARY KEY,
            business_name TEXT NOT NULL,
            business_description TEXT,
            business_category TEXT NOT NULL,
            address TEXT NOT NULL,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            area TEXT,
            phone TEXT,
            logo_url TEXT,
            is_verified INTEGER DEFAULT 0,
            average_rating REAL DEFAULT 0,
            total_reviews INTEGER DEFAULT 0,
            total_views INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    ''')
    
    # Products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY,
            vendor_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            original_price REAL,
            thumbnail_url TEXT,
            images TEXT,
            is_available INTEGER DEFAULT 1,
            stock_quantity INTEGER DEFAULT 0,
            average_rating REAL DEFAULT 0,
            total_reviews INTEGER DEFAULT 0,
            views_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vendor_id) REFERENCES vendors(user_id) ON DELETE CASCADE
        )
    ''')
    
    # Reviews table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            vendor_id TEXT NOT NULL,
            product_id TEXT,
            rating INTEGER NOT NULL,
            title TEXT,
            comment TEXT,
            vendor_response TEXT,
            images TEXT,
            helpful_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (customer_id) REFERENCES customers(user_id) ON DELETE CASCADE,
            FOREIGN KEY (vendor_id) REFERENCES vendors(user_id) ON DELETE CASCADE
        )
    ''')
    
    # Sample vendors for testing
    cursor.execute("SELECT COUNT(*) FROM vendors")
    if cursor.fetchone()[0] == 0:
        # Create sample vendor user
        sample_vendor_id = str(uuid.uuid4())
        hashed = bcrypt.hashpw("vendor123".encode('utf-8'), bcrypt.gensalt())
        cursor.execute('''
            INSERT INTO users (id, email, hashed_password, role, is_verified)
            VALUES (?, ?, ?, ?, ?)
        ''', (sample_vendor_id, "vendor@lako.com", hashed.decode('utf-8'), "vendor", 1))
        
        cursor.execute('''
            INSERT INTO vendors (user_id, business_name, business_category, address, latitude, longitude, area, phone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (sample_vendor_id, "Kuya's BBQ", "Street Foods", "Poblacion 1, Quipot", 14.6760, 121.0437, "Poblacion 1", "09123456789"))
        
        # Sample products
        products = [
            ("Spicy Siomai", "Best selling siomai with special sauce", "Dimsum", 25),
            ("Fishball (10pcs)", "Classic fishball with sweet and spicy sauce", "Street Food", 15),
            ("Kikiam (5pcs)", "Crispy kikiam with special dip", "Street Food", 20),
            ("Turon (Banana)", "Crispy banana rolls with langka", "Snacks", 15),
            ("BBQ Stick", "Grilled pork barbecue", "Street Food", 20)
        ]
        for p in products:
            cursor.execute('''
                INSERT INTO products (id, vendor_id, name, description, category, price)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (str(uuid.uuid4()), sample_vendor_id, p[0], p[1], p[2], p[3]))
    
    conn.commit()
    conn.close()

# ============================================
# PYDANTIC SCHEMAS
# ============================================

class CustomerRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: str
    phone: Optional[str] = None
    eula_accepted: bool = True

class VendorRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    business_name: str
    business_category: str
    address: str
    latitude: float
    longitude: float
    area: Optional[str] = None
    phone: Optional[str] = None
    eula_accepted: bool = True

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: str
    price: float
    stock_quantity: int = 0

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    is_available: Optional[bool] = None

class ReviewCreate(BaseModel):
    vendor_id: str
    product_id: Optional[str] = None
    rating: int = Field(..., ge=1, le=5)
    title: Optional[str] = None
    comment: Optional[str] = None

class InquiryResponse(BaseModel):
    inquiry_id: str
    response: str

# ============================================
# JWT UTILITIES
# ============================================

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except:
        return None

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

# ============================================
# FASTAPI APP
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Lako Backend...")
    init_db()
    print("Database initialized")
    yield
    print("Shutting down...")

app = FastAPI(title="Lako API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# HEALTH CHECK
# ============================================

@app.get("/")
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Lako API is running"}

# ============================================
# AUTH ENDPOINTS
# ============================================

@app.post("/api/auth/register/customer", response_model=TokenResponse)
async def register_customer(data: CustomerRegister):
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute("SELECT id FROM users WHERE email = ?", (data.email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt())
    
    cursor.execute('''
        INSERT INTO users (id, email, phone, hashed_password, role, eula_accepted_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, data.email, data.phone, hashed.decode('utf-8'), "customer", 
          datetime.utcnow().isoformat() if data.eula_accepted else None))
    
    # Create customer profile
    cursor.execute('''
        INSERT INTO customers (user_id, full_name)
        VALUES (?, ?)
    ''', (user_id, data.full_name))
    
    conn.commit()
    conn.close()
    
    token = create_access_token({"sub": user_id, "role": "customer"})
    return TokenResponse(access_token=token, user_id=user_id, role="customer")

@app.post("/api/auth/register/vendor", response_model=TokenResponse)
async def register_vendor(data: VendorRegister):
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Check if user exists
    cursor.execute("SELECT id FROM users WHERE email = ?", (data.email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create user
    user_id = str(uuid.uuid4())
    hashed = bcrypt.hashpw(data.password.encode('utf-8'), bcrypt.gensalt())
    
    cursor.execute('''
        INSERT INTO users (id, email, phone, hashed_password, role, eula_accepted_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, data.email, data.phone, hashed.decode('utf-8'), "vendor",
          datetime.utcnow().isoformat() if data.eula_accepted else None))
    
    # Create vendor profile
    cursor.execute('''
        INSERT INTO vendors (user_id, business_name, business_category, address, latitude, longitude, area, phone)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, data.business_name, data.business_category, data.address, 
          data.latitude, data.longitude, data.area, data.phone))
    
    conn.commit()
    conn.close()
    
    token = create_access_token({"sub": user_id, "role": "vendor"})
    return TokenResponse(access_token=token, user_id=user_id, role="vendor")

@app.post("/api/auth/login", response_model=TokenResponse)
async def login(data: LoginRequest):
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, hashed_password, role FROM users WHERE email = ? AND is_active = 1", (data.email,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user_id, hashed, role = row
    
    if not bcrypt.checkpw(data.password.encode('utf-8'), hashed.encode('utf-8')):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"sub": user_id, "role": role})
    return TokenResponse(access_token=token, user_id=user_id, role=role)

# ============================================
# VENDOR ENDPOINTS
# ============================================

@app.get("/api/vendor/profile")
async def get_vendor_profile(user: dict = Depends(get_current_user)):
    if user.get("role") != "vendor":
        raise HTTPException(status_code=403, detail="Vendor access required")
    
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT v.business_name, v.business_description, v.business_category, v.address, 
               v.latitude, v.longitude, v.area, v.phone, v.logo_url, v.is_verified,
               v.average_rating, v.total_reviews, v.total_views,
               u.email
        FROM vendors v
        JOIN users u ON v.user_id = u.id
        WHERE v.user_id = ?
    ''', (user["sub"],))
    
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    return {
        "business_name": row[0],
        "business_description": row[1],
        "business_category": row[2],
        "address": row[3],
        "latitude": row[4],
        "longitude": row[5],
        "area": row[6],
        "phone": row[7],
        "logo_url": row[8],
        "is_verified": bool(row[9]),
        "average_rating": row[10],
        "total_reviews": row[11],
        "total_views": row[12],
        "email": row[13]
    }

@app.get("/api/vendor/dashboard")
async def get_vendor_dashboard(user: dict = Depends(get_current_user)):
    if user.get("role") != "vendor":
        raise HTTPException(status_code=403, detail="Vendor access required")
    
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Get product stats
    cursor.execute('''
        SELECT COUNT(*), SUM(views_count), SUM(stock_quantity)
        FROM products WHERE vendor_id = ?
    ''', (user["sub"],))
    product_stats = cursor.fetchone()
    
    # Get review stats
    cursor.execute('''
        SELECT AVG(rating), COUNT(*) FROM reviews WHERE vendor_id = ?
    ''', (user["sub"],))
    review_stats = cursor.fetchone()
    
    conn.close()
    
    return {
        "total_products": product_stats[0] or 0,
        "total_views": product_stats[1] or 0,
        "total_stock": product_stats[2] or 0,
        "average_rating": round(review_stats[0], 1) if review_stats[0] else 0,
        "total_reviews": review_stats[1] or 0
    }

@app.get("/api/vendor/products")
async def get_vendor_products(user: dict = Depends(get_current_user)):
    if user.get("role") != "vendor":
        raise HTTPException(status_code=403, detail="Vendor access required")
    
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, name, description, category, price, original_price, 
               thumbnail_url, is_available, stock_quantity, average_rating, 
               total_reviews, views_count, created_at
        FROM products WHERE vendor_id = ? ORDER BY created_at DESC
    ''', (user["sub"],))
    
    rows = cursor.fetchall()
    conn.close()
    
    products = []
    for row in rows:
        products.append({
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "category": row[3],
            "price": row[4],
            "original_price": row[5],
            "thumbnail_url": row[6],
            "is_available": bool(row[7]),
            "stock_quantity": row[8],
            "average_rating": row[9],
            "total_reviews": row[10],
            "views_count": row[11],
            "created_at": row[12]
        })
    
    return {"products": products}

@app.post("/api/vendor/products")
async def create_product(data: ProductCreate, user: dict = Depends(get_current_user)):
    if user.get("role") != "vendor":
        raise HTTPException(status_code=403, detail="Vendor access required")
    
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    product_id = str(uuid.uuid4())
    
    cursor.execute('''
        INSERT INTO products (id, vendor_id, name, description, category, price, stock_quantity)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (product_id, user["sub"], data.name, data.description, data.category, data.price, data.stock_quantity))
    
    conn.commit()
    conn.close()
    
    return {"id": product_id, "message": "Product created"}

@app.delete("/api/vendor/products/{product_id}")
async def delete_product(product_id: str, user: dict = Depends(get_current_user)):
    if user.get("role") != "vendor":
        raise HTTPException(status_code=403, detail="Vendor access required")
    
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute("DELETE FROM products WHERE id = ? AND vendor_id = ?", (product_id, user["sub"]))
    conn.commit()
    conn.close()
    
    return {"message": "Product deleted"}

@app.get("/api/vendor/reviews")
async def get_vendor_reviews(user: dict = Depends(get_current_user)):
    if user.get("role") != "vendor":
        raise HTTPException(status_code=403, detail="Vendor access required")
    
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT r.id, r.rating, r.title, r.comment, r.created_at, c.full_name
        FROM reviews r
        JOIN customers c ON r.customer_id = c.user_id
        WHERE r.vendor_id = ?
        ORDER BY r.created_at DESC
    ''', (user["sub"],))
    
    rows = cursor.fetchall()
    conn.close()
    
    reviews = []
    for row in rows:
        reviews.append({
            "id": row[0],
            "rating": row[1],
            "title": row[2],
            "comment": row[3],
            "created_at": row[4],
            "customer_name": row[5]
        })
    
    return {"reviews": reviews}

@app.post("/api/vendor/reviews/{review_id}/reply")
async def reply_to_review(review_id: str, data: dict, user: dict = Depends(get_current_user)):
    if user.get("role") != "vendor":
        raise HTTPException(status_code=403, detail="Vendor access required")
    
    response = data.get("response")
    if not response:
        raise HTTPException(status_code=400, detail="Response required")
    
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE reviews SET vendor_response = ? WHERE id = ? AND vendor_id = ?
    ''', (response, review_id, user["sub"]))
    
    conn.commit()
    conn.close()
    
    return {"message": "Reply posted"}

# ============================================
# CUSTOMER ENDPOINTS
# ============================================

@app.get("/api/customer/vendors")
async def get_nearby_vendors(lat: float, lng: float, radius: float = 5):
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Simple bounding box for nearby vendors
    lat_delta = radius / 111.0
    lng_delta = radius / (111.0 * 1.0)  # Simplified
    
    cursor.execute('''
        SELECT v.user_id, v.business_name, v.business_category, v.address, 
               v.latitude, v.longitude, v.average_rating, v.total_reviews, v.logo_url
        FROM vendors v
        WHERE v.latitude BETWEEN ? AND ?
          AND v.longitude BETWEEN ? AND ?
          AND v.is_verified = 1
    ''', (lat - lat_delta, lat + lat_delta, lng - lng_delta, lng + lng_delta))
    
    rows = cursor.fetchall()
    conn.close()
    
    vendors = []
    for row in rows:
        vendors.append({
            "id": row[0],
            "name": row[1],
            "category": row[2],
            "address": row[3],
            "latitude": row[4],
            "longitude": row[5],
            "rating": row[6],
            "reviews": row[7],
            "logo": row[8]
        })
    
    return {"vendors": vendors}

@app.get("/api/customer/vendors/{vendor_id}")
async def get_vendor_details(vendor_id: str):
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT v.business_name, v.business_description, v.business_category, v.address,
               v.latitude, v.longitude, v.area, v.phone, v.logo_url, v.average_rating, v.total_reviews,
               u.email
        FROM vendors v
        JOIN users u ON v.user_id = u.id
        WHERE v.user_id = ?
    ''', (vendor_id,))
    
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # Get products
    cursor.execute('''
        SELECT id, name, description, category, price, thumbnail_url, average_rating
        FROM products WHERE vendor_id = ? AND is_available = 1
    ''', (vendor_id,))
    products = cursor.fetchall()
    
    conn.close()
    
    return {
        "vendor": {
            "name": row[0],
            "description": row[1],
            "category": row[2],
            "address": row[3],
            "latitude": row[4],
            "longitude": row[5],
            "area": row[6],
            "phone": row[7],
            "logo": row[8],
            "rating": row[9],
            "total_reviews": row[10],
            "email": row[11]
        },
        "products": [
            {
                "id": p[0],
                "name": p[1],
                "description": p[2],
                "category": p[3],
                "price": p[4],
                "image": p[5],
                "rating": p[6]
            }
            for p in products
        ]
    }

@app.post("/api/customer/reviews")
async def create_review(data: ReviewCreate, user: dict = Depends(get_current_user)):
    if user.get("role") != "customer":
        raise HTTPException(status_code=403, detail="Customer access required")
    
    conn = sqlite3.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    review_id = str(uuid.uuid4())
    
    cursor.execute('''
        INSERT INTO reviews (id, customer_id, vendor_id, product_id, rating, title, comment)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (review_id, user["sub"], data.vendor_id, data.product_id, data.rating, data.title, data.comment))
    
    # Update vendor average rating
    cursor.execute('''
        UPDATE vendors 
        SET average_rating = (SELECT AVG(rating) FROM reviews WHERE vendor_id = ?),
            total_reviews = (SELECT COUNT(*) FROM reviews WHERE vendor_id = ?)
        WHERE user_id = ?
    ''', (data.vendor_id, data.vendor_id, data.vendor_id))
    
    conn.commit()
    conn.close()
    
    return {"id": review_id, "message": "Review submitted"}

# ============================================
# RUN SERVER
# ============================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)