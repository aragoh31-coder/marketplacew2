from django.urls import path
from . import views

app_name = "anti_ddos"

urlpatterns = [
    path("spinner/", views.spinner, name="spinner"),
    path("status/", views.status, name="status"),
    path("pow/", views.pow_challenge, name="pow"),
    path("captcha/", views.captcha, name="captcha"),
    path("challenge/", views.challenge, name="challenge"),
]
