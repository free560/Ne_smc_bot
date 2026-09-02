from django.db import models
from django.conf import settings


class RiskSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='risk_settings')
    risk_per_trade = models.DecimalField(max_digits=4, decimal_places=2, default=1.0)
    daily_drawdown_limit = models.DecimalField(max_digits=4, decimal_places=2, default=5.0)
    weekly_drawdown_limit = models.DecimalField(max_digits=4, decimal_places=2, default=10.0)
    global_drawdown_limit = models.DecimalField(max_digits=4, decimal_places=2, default=20.0)
    max_open_positions = models.PositiveSmallIntegerField(default=5)
