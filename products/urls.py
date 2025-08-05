from django.urls import path

from . import views

app_name = "products"

urlpatterns = [
    path("", views.product_list, name="list"),
    path("<uuid:pk>/", views.product_detail, name="detail"),
    path("category/<int:category_id>/", views.products_by_category, name="by_category"),
]
