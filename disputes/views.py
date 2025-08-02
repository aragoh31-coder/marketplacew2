from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from .models import Dispute
from orders.models import Order


def dispute_list(request):
    disputes = Dispute.objects.all().order_by('-created_at')
    return render(request, 'disputes/list.html', {'disputes': disputes})


@login_required
def create_dispute(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        messages.success(request, 'Dispute created successfully.')
        return HttpResponseRedirect(reverse('disputes:list'))
    
    return render(request, 'disputes/create.html', {'order': order})


@login_required
def dispute_detail(request, dispute_id):
    dispute = get_object_or_404(Dispute, id=dispute_id)
    return render(request, 'disputes/detail.html', {'dispute': dispute})
