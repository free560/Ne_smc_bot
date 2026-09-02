from django.contrib import admin
from .models import Candle, FetchLog


@admin.register(Candle)
class CandleAdmin(admin.ModelAdmin):
    list_display = ("instrument", "timeframe", "timestamp", "open", "high", "low", "close")
    list_filter = ("instrument", "timeframe")
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)


@admin.register(FetchLog)
class FetchLogAdmin(admin.ModelAdmin):
    list_display = ("instrument", "timeframe", "success", "fetched_count", "created_at")
    list_filter = ("instrument", "timeframe", "success")
    ordering = ("-created_at",)
