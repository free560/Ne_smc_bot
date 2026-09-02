"""
apps/journal/forms.py
"""
from django import forms

from apps.journal.models import TradeJournalEntry

INPUT_CLASS = "w-full bg-gray-950 border border-gray-800 rounded px-3 py-2 text-sm text-gray-100"


class TradeJournalEntryForm(forms.ModelForm):
    class Meta:
        model = TradeJournalEntry
        fields = [
            "instrument", "direction", "entry", "stop_loss", "take_profit",
            "lot_size", "result", "pnl", "screenshot", "notes", "opened_at", "closed_at",
        ]
        widgets = {
            "instrument": forms.Select(attrs={"class": INPUT_CLASS}),
            "direction": forms.Select(attrs={"class": INPUT_CLASS}),
            "entry": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.00001"}),
            "stop_loss": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.00001"}),
            "take_profit": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.00001"}),
            "lot_size": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.01"}),
            "result": forms.Select(attrs={"class": INPUT_CLASS}),
            "pnl": forms.NumberInput(attrs={"class": INPUT_CLASS, "step": "0.01"}),
            "screenshot": forms.ClearableFileInput(attrs={"class": "text-sm text-gray-400"}),
            "notes": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
            "opened_at": forms.DateTimeInput(attrs={"class": INPUT_CLASS, "type": "datetime-local"}),
            "closed_at": forms.DateTimeInput(attrs={"class": INPUT_CLASS, "type": "datetime-local"}),
        }
