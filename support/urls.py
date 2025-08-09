from django.urls import path

from . import views

app_name = "support"

urlpatterns = [
    path("", views.support_home, name="home"),
    path("faq/", views.faq_view, name="faq"),
    path("tickets/", views.ticket_list, name="tickets"),
    path("tickets/create/", views.create_ticket, name="create_ticket"),
    path("tickets/<uuid:ticket_id>/", views.ticket_detail, name="ticket_detail"),
    path("feedback/", views.submit_feedback, name="feedback"),
    path("feedback/<uuid:order_id>/", views.leave_feedback, name="leave_feedback"),
]
