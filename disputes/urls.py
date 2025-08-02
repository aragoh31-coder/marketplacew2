from django.urls import path
from . import views

app_name = 'disputes'

urlpatterns = [
    path('', views.dispute_list, name='list'),
    path('create/<uuid:order_id>/', views.create_dispute, name='create'),
    path('<uuid:dispute_id>/', views.dispute_detail, name='detail'),
]
