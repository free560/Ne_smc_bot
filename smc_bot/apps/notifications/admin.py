from django.contrib import admin
from .models import NotificationLog, NotificationPreference


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "telegram_enabled", "email_enabled")


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("event_type", "channel", "user", "success", "created_at")
    list_filter = ("event_type", "channel", "success")
    ordering = ("-created_at",)
