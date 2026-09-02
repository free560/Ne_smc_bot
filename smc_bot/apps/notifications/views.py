"""
apps/notifications/views.py
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.notifications.forms import NotificationPreferenceForm
from apps.notifications.models import NotificationLog, NotificationPreference


@login_required
def overview(request):
    preference, _ = NotificationPreference.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = NotificationPreferenceForm(request.POST, instance=preference)
        if form.is_valid():
            form.save()
            return redirect("notifications:overview")
    else:
        form = NotificationPreferenceForm(instance=preference)

    logs = NotificationLog.objects.filter(user=request.user)[:50]

    context = {
        "module_title": "Notifications",
        "form": form,
        "logs": logs,
    }
    return render(request, "notifications/overview.html", context)
