import os
import sys
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Add apps directory to sys.path
sys.path.insert(0, str(BASE_DIR / 'apps'))

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-kodafriq-prod-ready-secret-key-2026')
DEBUG = True
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



# Email Notification Backend (Phase 10)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'Kodafriq Platform <notifications@kodafriq.com>'
