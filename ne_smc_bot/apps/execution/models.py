from django.db import models


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('filled', 'Filled'),
        ('cancelled', 'Cancelled'),
    ]
    MODE_CHOICES = [
        ('backtest', 'Backtest'),
        ('paper', 'Paper'),
        ('demo', 'Demo'),
        ('live', 'Live'),
    ]

    broker_account = models.ForeignKey('brokers.BrokerAccount', on_delete=models.CASCADE, related_name='orders')
    signal = models.ForeignKey('signals.Signal', on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    symbol = models.ForeignKey('scanner.Symbol', on_delete=models.CASCADE)
    direction = models.CharField(max_length=10)
    lot_size = models.DecimalField(max_digits=10, decimal_places=2)
    entry_price = models.DecimalField(max_digits=15, decimal_places=5)
    stop_loss = models.DecimalField(max_digits=15, decimal_places=5)
    take_profit = models.DecimalField(max_digits=15, decimal_places=5)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)


class Position(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='position')
    current_price = models.DecimalField(max_digits=15, decimal_places=5)
    pnl = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    is_open = models.BooleanField(default=True)
    is_breakeven_applied = models.BooleanField(default=False)
    trailing_stop_active = models.BooleanField(default=False)
    current_stop_loss = models.DecimalField(max_digits=15, decimal_places=5, null=True, blank=True)
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)


class Trade(models.Model):
    RESULT_CHOICES = [
        ('win', 'Win'),
        ('loss', 'Loss'),
        ('breakeven', 'Breakeven'),
    ]
    position = models.OneToOneField(Position, on_delete=models.CASCADE, related_name='trade')
    result = models.CharField(max_length=10, choices=RESULT_CHOICES)
    profit_loss = models.DecimalField(max_digits=15, decimal_places=2)
    closed_at = models.DateTimeField(auto_now_add=True)