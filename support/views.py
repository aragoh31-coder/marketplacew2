from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import SupportTicket


def support_home(request):
    recent_tickets = []
    if request.user.is_authenticated:
        recent_tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')[:5]
    return render(request, 'support/home.html', {'recent_tickets': recent_tickets})


def faq_view(request):
    return render(request, 'support/faq.html')


@login_required
def ticket_list(request):
    tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'support/tickets.html', {'tickets': tickets})


@login_required
def create_ticket(request):
    if request.method == 'POST':
        messages.success(request, 'Support ticket created successfully.')
    return render(request, 'support/create_ticket.html')


@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id, user=request.user)
    return render(request, 'support/ticket_detail.html', {'ticket': ticket})


@login_required
def submit_feedback(request):
    return render(request, 'support/feedback.html')


@login_required
def leave_feedback(request, order_id):
    return render(request, 'support/feedback.html', {'order': {'id': order_id}})
