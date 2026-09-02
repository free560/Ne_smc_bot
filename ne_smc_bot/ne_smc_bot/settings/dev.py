from .base import *
from decouple import config

DEBUG = True
ALLOWED_HOSTS = ['*']

LIVE_TRADING_ENABLED = False

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'