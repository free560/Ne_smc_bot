from django.db import models


class BacktestResult(models.Model):
    symbol = models.ForeignKey('scanner.Symbol', on_delete=models.CASCADE)
    timeframe = models.CharField(max_length=5)
    start_date = models.DateField()
    end_date = models.DateField()
    win_rate = models.DecimalField(max_digits=5, decimal_places=2)
    profit_factor = models.DecimalField(max_digits=6, decimal_places=2)
    drawdown = models.DecimalField(max_digits=5, decimal_places=2)
    net_profit = models.DecimalField(max_digits=15, decimal_places=2)
    sharpe_ratio = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)