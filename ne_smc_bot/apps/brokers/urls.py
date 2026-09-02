from django.urls import path
from apps.brokers import views

urlpatterns = [
    path('brokers/', views.broker_management, name='broker_management'),
    path('brokers/disconnect/<int:account_id>/', views.disconnect_broker, name='disconnect_broker'),
]