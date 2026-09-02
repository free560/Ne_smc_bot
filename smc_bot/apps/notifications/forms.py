"""
apps/notifications/forms.py
"""
from django import forms

from apps.notifications.models import NotificationPreference

INPUT_CLASS = "w-full bg-gray-950 border border-gray-800 rounded px-3 py-2 text-sm text-gray-100"


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = [
            "telegram_enabled", "email_enabled", "email_override",
            "notify_on_signal", "notify_on_risk_alert", "notify_on_range_market",
        ]
        widgets = {
            "email_override": forms.EmailInput(attrs={"class": INPUT_CLASS, "placeholder": "optionnel"}),
        }
