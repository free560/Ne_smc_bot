from django.db import models


class TradeJournal(models.Model):
    trade = models.OneToOneField('execution.Trade', on_delete=models.CASCADE, related_name='journal_entry')
    notes = models.TextField(blank=True)
    screenshot = models.ImageField(upload_to='journal_screenshots/', blank=True, null=True)
    lessons_learned = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)