from django.urls import path
from . import views

app_name = "scanner"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("trigger/", views.trigger_scan, name="trigger_scan"),
]
