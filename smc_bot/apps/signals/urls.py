from django.urls import path
from . import views

app_name = "signals"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("scan/", views.run_scan_now, name="run_scan_now"),
]
