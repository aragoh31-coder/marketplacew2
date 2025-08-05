import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

def get_env_var(var_name):
    try:
        return os.environ[var_name]
    except KeyError:
        raise ImproperlyConfigured(f"Set the {var_name} environment variable.")

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = get_env_var("DJANGO_SECRET_KEY")
DEBUG = get_env_var("DJANGO_DEBUG") == "True"
ALLOWED_HOSTS = get_env_var("DJANGO_ALLOWED_HOSTS").split(",")

DATABASES = {
    "default": {
        "ENGINE": get_env_var("DB_ENGINE"),
        "NAME": get_env_var("DB_NAME"),
        "USER": get_env_var("DB_USER"),
        "PASSWORD": get_env_var("DB_PASSWORD"),
        "HOST": get_env_var("DB_HOST"),
        "PORT": get_env_var("DB_PORT"),
    }
}
