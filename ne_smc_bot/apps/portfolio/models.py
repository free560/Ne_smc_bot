from django.db import models


class Portfolio(models.Model):
    broker_account = models.ForeignKey('brokers.BrokerAccount', on_delete=models.CASCADE, related_name='portfolio_snapshots')
    balance = models.DecimalField(max_digits=15, decimal_places=2)
    equity = models.DecimalField(max_digits=15, decimal_places=2)
    snapshot_date = models.DateTimeField(auto_now_add=True)