from django.contrib import admin
from .models import UserProfile, AuditLog


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "telegram_chat_id", "created_at")
    list_filter = ("role",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "user", "ip_address", "created_at")
    list_filter = ("action",)
    ordering = ("-created_at",)
