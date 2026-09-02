from django.contrib import admin
from .models import SignalRecord


@admin.register(SignalRecord)
class SignalRecordAdmin(admin.ModelAdmin):
    list_display = ("instrument", "direction", "scenario", "confidence_score",
                     "risk_reward", "generated_at")
    list_filter = ("instrument", "direction", "scenario")
    date_hierarchy = "generated_at"
    ordering = ("-generated_at",)
