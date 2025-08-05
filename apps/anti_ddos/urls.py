from django.urls import path

from .views import challenge

app_name = "anti_ddos"
urlpatterns = [
    path("challenge/", challenge, name="challenge"),
]
