from pathlib import Path
from datetime import timedelta
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-8j*(28(_98)x$2d+io267_@ki*-$wh1oea4th=b23th0!)=im7'

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0ae745a8c873.ngrok-free.app']

# Daphne must come first for Channels to work properly
INSTALLED_APPS = [
    'daphne',  # Daphne must come before django.contrib.staticfiles
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'channels',  # Django Channels
    'users',
    'services',
    'requests',
    'locations',
    'images',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
THUMBNAIL_SIZE = (300, 300)
MAX_IMAGE_SIZE = 5242880

# ASGI configuration for Django Channels
ASGI_APPLICATION = 'config.asgi.application'

# Django Channels Redis Configuration
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],  # Redis server address and port
            # Optional Redis configuration:
            # "password": "yourpassword",  # If Redis has password
            # "db": 0,  # Redis database number (default 0)
            # "prefix": "vehix",  # Optional: prefix for Redis keys
            # "socket_timeout": 5,  # Connection timeout in seconds
            # "socket_connect_timeout": 5,  # Socket connection timeout
            # "socket_keepalive": True,  # Enable TCP keepalive
            # "retry_on_timeout": True,  # Retry on timeout
        },
    },
}

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

CORS_PREFLIGHT_MAX_AGE = 86400

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.AllowAny',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'USER_AUTHENTICATION_RULE': 'rest_framework_simplejwt.authentication.default_user_authentication_rule',
    'TOKEN_TYPE_CLAIM': 'token_type',
    'JTI_CLAIM': 'jti',
}

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Both WSGI and ASGI should be configured
WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'TUTU',
        'USER': 'postgres',
        'PASSWORD': 'TUTU2005',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

AUTH_USER_MODEL = 'users.User'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Africa/Kampala'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'corsheaders': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
        'channels': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}

PESAPAL_CONSUMER_KEY = 'hezvEw5rc1nMNtfIZ0D4yVmHSAbV4VDw'
PESAPAL_CONSUMER_SECRET = 'Ay7z5caeDyKyqim8M7NuR9MjGU4='
PESAPAL_URL = 'https://pay.pesapal.com/v3'
PESAPAL_IPN_URL = 'https://0ae745a8c873.ngrok-free.app/api/payments/pesapal/ipn/'
PESAPAL_IPN_ID = ''
CSRF_TRUSTED_ORIGINS = ['https://0ae745a8c873.ngrok-free.app']