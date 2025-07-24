from django.urls import path
from . import views

app_name = 'security'

urlpatterns = [
    path('status/', views.security_status, name='security_status'),
    path('dashboard/', views.user_security_dashboard, name='user_dashboard'),
    path('settings/', views.security_settings, name='settings'),
    path('bot-challenge/', views.bot_challenge, name='bot_challenge'),
    path('rate-limited/', views.rate_limited, name='rate_limited'),
    path('security-verification/', views.security_verification, name='security_verification'),
    path('api/status/', views.security_status_api, name='security_status_api'),
    path('ip-change/', views.ip_change_detected, name='ip_change_detected'),
    path('session-expired/', views.session_expired, name='session_expired'),
]
