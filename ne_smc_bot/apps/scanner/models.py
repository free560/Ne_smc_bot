from django.db import models


class Symbol(models.Model):
    ASSET_CLASS_CHOICES = [
        ('forex', 'Forex'),
        ('crypto', 'Crypto'),
        ('metals', 'Metals'),
    ]
    name = models.CharField(max_length=20, unique=True)
    asset_class = models.CharField(max_length=20, choices=ASSET_CLASS_CHOICES)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class MarketData(models.Model):
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE, related_name='market_data')
    timeframe = models.CharField(max_length=5)
    timestamp = models.DateTimeField()
    open = models.DecimalField(max_digits=15, decimal_places=5)
    high = models.DecimalField(max_digits=15, decimal_places=5)
    low = models.DecimalField(max_digits=15, decimal_places=5)
    close = models.DecimalField(max_digits=15, decimal_places=5)
    volume = models.BigIntegerField(default=0)

    class Meta:
        unique_together = ('symbol', 'timeframe', 'timestamp')
        indexes = [models.Index(fields=['symbol', 'timeframe', 'timestamp'])]

    
    def __str__(self):
        return f"{self.symbol.name} {self.timeframe} @ {self.timestamp}"   