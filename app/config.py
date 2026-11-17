import os
from urllib.parse import quote_plus
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'supermarket-secret-key-prod-98317-super-secure')
    
    # MySQL Database Config
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '3306')
    DB_NAME = os.getenv('DB_NAME', 'smart_supermarket')
    
    # Try MySQL URI if explicitly requested or if configured
    USE_SQLITE = os.getenv('USE_SQLITE', 'false').lower() in ('true', '1', 't')
    
    if USE_SQLITE:
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'supermarket.db')}"
    else:
        # Default MySQL connection string using PyMySQL (properly URL-encoded for special characters in passwords)
        encoded_user = quote_plus(DB_USER)
        encoded_password = quote_plus(DB_PASSWORD)
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{encoded_user}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
        )
    
    # Fallback SQLite path if MySQL server is unreachable
    SQLITE_FALLBACK_URI = f"sqlite:///{os.path.join(BASE_DIR, 'supermarket.db')}"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,
        'pool_pre_ping': True,
    }
    
    # Store settings
    STORE_NAME = os.getenv('STORE_NAME', 'Smart Supermarket & HyperMart')
    STORE_ADDRESS = os.getenv('STORE_ADDRESS', '100 Market Boulevard, Central Commercial District')
    STORE_PHONE = os.getenv('STORE_PHONE', '+1 (555) 987-6543')
    STORE_EMAIL = os.getenv('STORE_EMAIL', 'billing@smartsupermarket.com')
    STORE_TAX_NUMBER = os.getenv('STORE_TAX_NUMBER', 'GSTIN-98AABCS1234F1Z8')
    STORE_DEFAULT_TAX_RATE = float(os.getenv('STORE_DEFAULT_TAX_RATE', '5.0')) # 5% default tax
