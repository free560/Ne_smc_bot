"""
SMC RSI BOOM & CRASH 1000 PRO BOT
Configuration Django - config/settings.py

Architecture : Django MVT + Service Layer Pattern
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# --------------------------------------------------------------------------
# SÉCURITÉ
# --------------------------------------------------------------------------
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-CHANGE-ME-IN-PRODUCTION",
)

DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# --------------------------------------------------------------------------
# APPLICATIONS
# --------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
]

THIRD_PARTY_APPS = [
    # "rest_framework",       # activé en Phase 3 (API pour le dashboard / mobile)
    # "django_celery_beat",   # activé quand le scanner tournera en tâches planifiées
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.dashboard",
    "apps.market_data",
    "apps.scanner",
    "apps.smc",
    "apps.indicators",
    "apps.signals",
    "apps.risk",
    "apps.journal",
    "apps.analytics",
    "apps.notifications",
    "apps.settings_app",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --------------------------------------------------------------------------
# BASE DE DONNÉES (SQLite par défaut, comme demandé dans le cahier des charges)
# --------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# --------------------------------------------------------------------------
# VALIDATION DES MOTS DE PASSE
# --------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --------------------------------------------------------------------------
# INTERNATIONALISATION
# --------------------------------------------------------------------------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Bujumbura"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------
# FICHIERS STATIQUES & MÉDIA
# --------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# AUTHENTIFICATION
# --------------------------------------------------------------------------
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:overview"
LOGOUT_REDIRECT_URL = "accounts:login"

# --------------------------------------------------------------------------
# PARAMÈTRES MÉTIER PAR DÉFAUT (Risk Management)
# Surchargés ensuite via apps.settings_app (Phase 4+)
# --------------------------------------------------------------------------
TRADING_DEFAULTS = {
    "RISK_PER_TRADE_PERCENT": 1.0,           # 0.5 / 1 / 2 %
    "MIN_RISK_REWARD": 2.0,                  # 1:2 minimum
    "MAX_POSITIONS_PER_SETUP": 2,
    "MAX_CONSECUTIVE_LOSSES": 3,
    "MAX_DAILY_DRAWDOWN_PERCENT": 20.0,
    "RSI_PERIOD": 14,
    "RSI_TIMEFRAME": "M1",
    "STRUCTURE_TIMEFRAME": "M30",
    "CONFIRMATION_TIMEFRAME": "M15",
    "INSTRUMENTS": ["BOOM1000", "CRASH1000"],
}

# --------------------------------------------------------------------------
# CELERY (préparé pour le scanner temps réel + notifications async)
# --------------------------------------------------------------------------
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# --------------------------------------------------------------------------
# DERIV API (préparé pour market_data - WebSocket)
# --------------------------------------------------------------------------
DERIV_APP_ID = os.environ.get("DERIV_APP_ID", "")
DERIV_API_TOKEN = os.environ.get("DERIV_API_TOKEN", "")
DERIV_WS_URL = os.environ.get("DERIV_WS_URL", "wss://ws.derivws.com/websockets/v3")

# --------------------------------------------------------------------------
# NOTIFICATIONS (Telegram / Email)
# --------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"  # console en dev
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@smcbot.local")

# --------------------------------------------------------------------------
# LOGGING
# --------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} - {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "smc_bot.log",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "apps": {"handlers": ["console", "file"], "level": "DEBUG", "propagate": False},
    },
}
