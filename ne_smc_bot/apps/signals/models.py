from django.db import models


class Signal(models.Model):
    DIRECTION_CHOICES = [
        ('buy', 'Buy'),
        ('sell', 'Sell'),
        ('no_trade', 'No Trade'),
    ]

    symbol = models.ForeignKey('scanner.Symbol', on_delete=models.CASCADE, related_name='signals')
    timeframe = models.CharField(max_length=5)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
    entry_price = models.DecimalField(max_digits=15, decimal_places=5)
    stop_loss = models.DecimalField(max_digits=15, decimal_places=5)
    take_profit = models.DecimalField(max_digits=15, decimal_places=5)
    risk_reward = models.DecimalField(max_digits=6, decimal_places=2)
    confidence_score = models.PositiveSmallIntegerField(default=0)
    reason = models.TextField(blank=True)
    is_evaluated = models.BooleanField(default=False)
    lot_size = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    execution_allowed = models.BooleanField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.symbol} {self.direction} @ {self.entry_price}"