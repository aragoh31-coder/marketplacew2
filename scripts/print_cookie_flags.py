import os
from django.conf import settings

print("ALLOW_INSECURE_ONION_COOKIES =", os.environ.get("ALLOW_INSECURE_ONION_COOKIES"))
print("SESSION_COOKIE_SECURE       =", settings.SESSION_COOKIE_SECURE)
print("CSRF_COOKIE_SECURE          =", settings.CSRF_COOKIE_SECURE)
