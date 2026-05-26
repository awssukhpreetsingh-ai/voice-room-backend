# from pathlib import Path
# from dotenv import load_dotenv
# import os

# load_dotenv()

# BASE_DIR = Path(__file__).resolve().parent.parent
# SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret-change-in-prod')
# DEBUG = os.getenv('DEBUG', 'True') == 'True'
# ALLOWED_HOSTS = ['*']

# INSTALLED_APPS = [
#     'django.contrib.auth',        # ✅ REQUIRED
#     'django.contrib.contenttypes',
#     'django.contrib.sessions',    # ✅ REQUIRED
#     'django.contrib.staticfiles',
#     'rest_framework',
#     'corsheaders',
#     'rooms',
# ]
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': BASE_DIR / 'db.sqlite3',
#     }
# }

# MIDDLEWARE = [
#     'corsheaders.middleware.CorsMiddleware',
#     'django.middleware.common.CommonMiddleware',
# ]

# ROOT_URLCONF = 'core.urls'
# WSGI_APPLICATION = 'core.wsgi.application'

# # ── No database needed — rooms live in Redis ──

# # ── Redis ─────────────────────────────────────
# REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
# REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
# REDIS_DB   = int(os.getenv('REDIS_DB',   0))

# # Room TTL — rooms auto-expire after 24 hours of inactivity
# ROOM_TTL_SECONDS = int(os.getenv('ROOM_TTL_SECONDS', 86400))

# # ── LiveKit ────────────────────────────────────
# LIVEKIT_API_KEY    = os.getenv('LIVEKIT_API_KEY',    'APInLABZP5oGjq7')
# LIVEKIT_API_SECRET = os.getenv('LIVEKIT_API_SECRET', 'YHS2Dh0ffCmd29Tn1F5Wqt5k2O937pfmA7m3YM6vm0HA')
# LIVEKIT_HOST       = os.getenv('LIVEKIT_HOST',       'wss://testingtesting-nmm2qflg.livekit.cloud')

# # ── DRF ────────────────────────────────────────
# REST_FRAMEWORK = {
#     'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
#     'DEFAULT_PARSER_CLASSES':   ['rest_framework.parsers.JSONParser'],
# }

# # ── CORS — allow Flutter app ────────────────────
# CORS_ALLOW_ALL_ORIGINS = True   # tighten this in production

# STATIC_URL = '/static/'
# DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'



from pathlib import Path
from dotenv import load_dotenv
import os

import dj_database_url

# Explicitly point at core/.env so this works regardless of where manage.py is run from.
load_dotenv(dotenv_path=Path(__file__).resolve().parent / '.env')

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-secret-change-in-prod')
DEBUG      = os.getenv('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'storages',
    'rooms',
    'users',
    'spaces',
    'notifications',
    'admin_panel',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.security.SecurityMiddleware',
]

ROOT_URLCONF    = 'core.urls'
WSGI_APPLICATION = 'core.wsgi.application'

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql',
#         'NAME': os.getenv('DB_NAME', 'wavroom_db'),
#         'USER': os.getenv('DB_USER', 'wavroom_user'),
#         'PASSWORD': os.getenv('DB_PASSWORD', 'tN16cEZiPuR231M8sBMK'),
#         'HOST': os.getenv('DB_HOST', 'localhost'),
#         'PORT': os.getenv('DB_PORT', '5432'),
#     }
# }

DATABASES = {
    'default': dj_database_url.parse(
        os.getenv("DATABASE_URL"),
        conn_max_age=0,
        ssl_require=True,
        conn_health_checks=True,
    )
}
# Supabase PgBouncer doesn't support server-side named cursors.
DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True

# ── MongoDB Atlas ──────────────────────────────
MONGODB_URI = os.getenv('MONGODB_URI', '')

# ── Redis ──────────────────────────────────────
REDIS_HOST       = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT       = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB         = int(os.getenv('REDIS_DB',   0))
ROOM_TTL_SECONDS = int(os.getenv('ROOM_TTL_SECONDS', 14400))  # 4 hours default

# ── LiveKit ────────────────────────────────────
LIVEKIT_API_KEY    = os.getenv('LIVEKIT_API_KEY',    'APInLABZP5oGjq7')
LIVEKIT_API_SECRET = os.getenv('LIVEKIT_API_SECRET', 'YHS2Dh0ffCmd29Tn1F5Wqt5k2O937pfmA7m3YM6vm0HA')
LIVEKIT_HOST       = os.getenv('LIVEKIT_HOST',       'wss://testingtesting-nmm2qflg.livekit.cloud')

# ── Firebase Admin ─────────────────────────────
FIREBASE_CREDENTIALS = os.getenv(
    'FIREBASE_CREDENTIALS',
    str(BASE_DIR / 'firebase-credentials.json')
)

# ── DRF ───────────────────────────────────────
# Views authenticate manually via _get_user() using wavroom_ tokens.
# AllowAny lets requests reach the views; each view returns 401 itself if the
# token is missing or invalid. JWTAuthentication is NOT used — removing it
# prevents DRF from rejecting wavroom_ tokens before views can handle them.
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES':  ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES':    ['rest_framework.parsers.JSONParser'],
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.AllowAny'],
}

# ── CORS ───────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = True

STATIC_URL = '/static/'

# ── AWS S3 Storage ─────────────────────────────
AWS_ACCESS_KEY_ID       = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY   = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME', 'voice-room-images')
AWS_S3_REGION_NAME      = os.getenv('AWS_S3_REGION_NAME', 'ap-south-1')
AWS_S3_CUSTOM_DOMAIN    = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com'
AWS_DEFAULT_ACL         = None   # bucket has ACLs disabled (Object Ownership = Bucket owner enforced)
AWS_S3_FILE_OVERWRITE   = True
AWS_QUERYSTRING_AUTH    = False

STORAGES = {
    'default': {
        'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}
MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'