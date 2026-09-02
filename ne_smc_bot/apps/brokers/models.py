from django.db import models
from django.conf import settings
from core.security.encryption import encrypt_value, decrypt_value


class BrokerAccount(models.Model):
    BROKER_CHOICES = [
        ('deriv', 'Deriv'),
        ('exness', 'Exness'),
    ]
    ACCOUNT_TYPE_CHOICES = [
        ('demo', 'Demo'),
        ('live', 'Live'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='broker_accounts')
    broker_name = models.CharField(max_length=50, choices=BROKER_CHOICES)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    api_key = models.CharField(max_length=255)
    api_secret = models.CharField(max_length=255)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    is_connected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def set_credentials(self, api_key: str, api_secret: str = ''):
        self.api_key = encrypt_value(api_key)
        self.api_secret = encrypt_value(api_secret) if api_secret else ''

    def get_api_key(self) -> str:
        return decrypt_value(self.api_key)

    def get_api_secret(self) -> str:
        return decrypt_value(self.api_secret) if self.api_secret else ''

    def __str__(self):
        return f"{self.broker_name} - {self.account_type} ({self.user})"

