from django.urls import path
from . import views

app_name = "risk"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("lot-size/", views.position_size_calculator, name="position_size_calculator"),
]
