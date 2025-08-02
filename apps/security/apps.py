from django.apps import AppConfig


class SecurityConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.security'
    verbose_name = 'Security'
    
    def ready(self):
        from .performance_monitor import security_monitor
        security_monitor.start_monitoring()
