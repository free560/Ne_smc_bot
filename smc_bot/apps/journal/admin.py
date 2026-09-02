from django.contrib import admin
from .models import TradeJournalEntry


@admin.register(TradeJournalEntry)
class TradeJournalEntryAdmin(admin.ModelAdmin):
    list_display = ("user", "instrument", "direction", "result", "pnl", "opened_at")
    list_filter = ("instrument", "direction", "result")
    date_hierarchy = "opened_at"
