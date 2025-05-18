import os
import secrets
from datetime import timedelta
from dotenv import load_dotenv
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(16))
PERMANENT_SESSION_LIFETIME = timedelta(days=30)
DEBUG = bool(os.getenv('DEBUG', 'False'))

DB_CONFIG = {
    'user': os.getenv('DB_USER', ''),
    'password': os.getenv('DB_PASSWORD', ''),
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'rater'),
    'pool_name': 'rater_pool',
    'pool_size': 5
}

OSU_CLIENT_ID = os.getenv('OSU_CLIENT_ID')
OSU_CLIENT_SECRET = os.getenv('OSU_CLIENT_SECRET')
OSU_REDIRECT_URI = os.getenv('OSU_REDIRECT_URI', 'http://localhost:5000/callback')