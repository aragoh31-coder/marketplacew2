from django.urls import path
from . import views
from . import totp_views

app_name = 'accounts'

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/settings/', views.profile_settings, name='profile_settings'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('profile/pgp/', views.pgp_settings, name='pgp_settings'),
    path('profile/pgp/verify/', views.pgp_verify_key, name='pgp_verify'),
    path('profile/pgp/remove/', views.pgp_remove_key, name='pgp_remove'),
    path('profile/delete/', views.delete_account, name='delete_account'),
    path('profile/login-history/', views.login_history_view, name='login_history'),
    path('pgp-challenge/', views.pgp_challenge_view, name='pgp_challenge'),
    path('pgp-login/', views.pgp_challenge_view, name='pgp_login'),
    path('test-pgp/', views.test_pgp_encryption, name='test_pgp'),
    
    path('settings/totp/', views.totp_settings, name='totp_settings'),
    path('settings/totp/setup/', views.totp_setup, name='totp_setup'),
    path('settings/totp/backup-codes/', views.totp_backup_codes, name='totp_backup_codes'),
    path('auth/totp/', views.verify_totp, name='verify_totp'),
    
    path('2fa/setup/', totp_views.totp_setup, name='totp_setup'),
    path('2fa/verify/', totp_views.totp_verify, name='totp_verify'),
    path('2fa/settings/', totp_views.totp_settings, name='totp_settings'),
    path('2fa/disable/', totp_views.totp_disable, name='totp_disable'),
    path('2fa/backup-codes/regenerate/', totp_views.regenerate_backup_codes, name='regenerate_backup_codes'),
    path('2fa/test/', totp_views.test_totp, name='test_totp'),
]
