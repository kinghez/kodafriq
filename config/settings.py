import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv(Path(__file__).resolve().parent.parent / '.env')

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Add apps directory to sys.path
sys.path.insert(0, str(BASE_DIR / 'apps'))

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-kodafriq-prod-ready-secret-key-2026')
DEBUG = os.environ.get('DJANGO_DEBUG', os.environ.get('DEBUG', 'True')).lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = [
    '*',
    '.ngrok-free.app',
    '.ngrok.io',
    '.ngrok.app',
    '.ngrok-free.dev',
    'localhost',
    '127.0.0.1',
]

# CSRF Trusted Origins for Ngrok Tunnels & Local Development
CSRF_TRUSTED_ORIGINS = [
    'https://kodafriq.com',
    'https://www.kodafriq.com',
    'http://kodafriq.com',
    'http://www.kodafriq.com',
    'http://72.61.146.171',
    'https://*.ngrok-free.app',
    'https://*.ngrok.io',
    'https://*.ngrok.app',
    'https://*.ngrok-free.dev',
    'http://*.ngrok-free.app',
    'http://*.ngrok.io',
    'http://*.ngrok.app',
    'http://127.0.0.1',
    'http://localhost',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
]

# Reverse Proxy & Tunnel Headers for Ngrok SSL
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Kodafriq Core Modules
    'apps.core.apps.CoreConfig',
    'apps.accounts.apps.AccountsConfig',
    'apps.skills.apps.SkillsConfig',
    'apps.assessments.apps.AssessmentsConfig',
    'apps.scoring.apps.ScoringConfig',
    'apps.employers.apps.EmployersConfig',
    'apps.training.apps.TrainingConfig',
    'apps.dashboard.apps.DashboardConfig',
    'apps.notifications.apps.NotificationsConfig',
    'apps.contracts.apps.ContractsConfig',
    'apps.billing.apps.BillingConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Kodafriq Security, Visitor Intelligence & Audit Middleware (Phase 10)
    'apps.core.middleware.VisitorTrackingMiddleware',
    'apps.core.middleware.AccountSecurityMiddleware',
    'apps.core.middleware.AuditLoggingMiddleware',
    'apps.core.middleware.CustomPermissionDeniedMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.core.context_processors.platform_context',
                'apps.dashboard.context_processors.notification_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database
# Database Configuration (PostgreSQL in Production, SQLite in Development)
DB_ENGINE = os.environ.get('DB_ENGINE', '')
DB_NAME = os.environ.get('DB_NAME', '')

if 'postgresql' in DB_ENGINE.lower() or DB_NAME:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': DB_NAME or os.environ.get('POSTGRES_DB', 'kodafriq_db'),
            'USER': os.environ.get('DB_USER', os.environ.get('POSTGRES_USER', 'kodafriq_user')),
            'PASSWORD': os.environ.get('DB_PASSWORD', os.environ.get('POSTGRES_PASSWORD', '')),
            'HOST': os.environ.get('DB_HOST', os.environ.get('POSTGRES_HOST', 'localhost')),
            'PORT': os.environ.get('DB_PORT', os.environ.get('POSTGRES_PORT', '5432')),
            'CONN_MAX_AGE': int(os.environ.get('DB_CONN_MAX_AGE', 600)),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static & Media Assets
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Authentication Redirection
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:home'
LOGOUT_REDIRECT_URL = 'core:home'

# Default auto field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'



# Dynamic Email Notification Backend (One.com, Hostinger, SendGrid, etc.)
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 465))

use_ssl_env = os.environ.get('EMAIL_USE_SSL')
use_tls_env = os.environ.get('EMAIL_USE_TLS')

if use_ssl_env is not None:
    EMAIL_USE_SSL = use_ssl_env.lower() in ('true', '1', 'yes')
    EMAIL_USE_TLS = not EMAIL_USE_SSL
elif use_tls_env is not None:
    EMAIL_USE_TLS = use_tls_env.lower() in ('true', '1', 'yes')
    EMAIL_USE_SSL = not EMAIL_USE_TLS
else:
    # Auto-detect mutually exclusive mode by port (Port 465 is SSL, 587 is TLS)
    if EMAIL_PORT == 465:
        EMAIL_USE_SSL = True
        EMAIL_USE_TLS = False
    else:
        EMAIL_USE_TLS = True
        EMAIL_USE_SSL = False

EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Kodafriq Platform <notifications@kodafriq.com>')
PLATFORM_URL = os.environ.get('PLATFORM_URL', 'https://kodafriq.com')
