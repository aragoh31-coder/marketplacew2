from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("cart/", views.cart_view, name="cart"),
    path("add-to-cart/<uuid:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("", views.order_list, name="list"),
    path("<uuid:pk>/", views.order_detail, name="detail"),
]
