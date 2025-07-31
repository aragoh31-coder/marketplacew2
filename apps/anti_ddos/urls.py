from django.urls import path
from .views import challenge_view, verify_view

app_name = 'anti_ddos'
urlpatterns = [
    path('challenge/', challenge_view, name='challenge'),
    path('verify/', verify_view, name='verify'),
]
