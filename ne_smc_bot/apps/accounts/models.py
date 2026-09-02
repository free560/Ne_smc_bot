from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    email = models.EmailField(blank=True, null=True, unique=True)

    # Telegram sert uniquement à recevoir des notifications, pas à se connecter
    telegram_chat_id = models.CharField(max_length=50, blank=True, null=True)

    is_live_trading_allowed = models.BooleanField(default=False)

    def __str__(self):
        return self.username or self.email