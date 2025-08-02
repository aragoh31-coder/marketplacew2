from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from .models import Order, Dispute, DisputeMessage, DisputeEvidence, DisputeTimeline
from .dispute_forms import RaiseDisputeForm, DisputeMessageForm, DisputeEvidenceForm, AdminDisputeResolutionForm

@login_required
def raise_dispute(request, order_id):
    """Raise a new dispute for an order"""
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    
    if not order.can_be_disputed():
        messages.error(request, "This order cannot be disputed at this time.")
        return redirect('orders:detail', order_id=order.id)
    
    if order.has_active_dispute():
        messages.error(request, "This order already has an active dispute.")
        return redirect('orders:disputes', order_id=order.id)
    
    if request.method == 'POST':
        form = RaiseDisputeForm(request.POST)
        if form.is_valid():
            dispute = form.save(commit=False)
            dispute.order = order
            dispute.raised_by = request.user
            dispute.save()
            
            DisputeTimeline.objects.create(
                dispute=dispute,
                action_type='created',
                actor=request.user,
                description=f"Dispute created: {dispute.title}",
                metadata={'dispute_type': dispute.dispute_type}
            )
            
            messages.success(request, "Dispute has been raised successfully.")
            return redirect('orders:dispute_detail', dispute_id=dispute.id)
    else:
        form = RaiseDisputeForm()
    
    return render(request, 'orders/raise_dispute.html', {
        'form': form,
        'order': order
    })

@login_required
def dispute_detail(request, dispute_id):
    """View dispute details and messages"""
    dispute = get_object_or_404(Dispute, id=dispute_id)
    
    if request.user not in dispute.get_participants() and not request.user.is_staff:
        raise Http404("Dispute not found")
    
    messages_list = dispute.messages.all()
    evidence_list = dispute.evidence.all()
    timeline = dispute.timeline.all()
    
    message_form = DisputeMessageForm()
    evidence_form = DisputeEvidenceForm()
    
    if request.method == 'POST':
        if 'add_message' in request.POST:
            message_form = DisputeMessageForm(request.POST)
            if message_form.is_valid():
                message = message_form.save(commit=False)
                message.dispute = dispute
                message.sender = request.user
                message.message_type = 'admin' if request.user.is_staff else 'user'
                message.save()
                
                DisputeTimeline.objects.create(
                    dispute=dispute,
                    action_type='message_added',
                    actor=request.user,
                    description=f"Message added by {request.user.username}",
                    metadata={'message_id': str(message.id)}
                )
                
                messages.success(request, "Message added successfully.")
                return redirect('orders:dispute_detail', dispute_id=dispute.id)
        
        elif 'add_evidence' in request.POST:
            evidence_form = DisputeEvidenceForm(request.POST, request.FILES)
            if evidence_form.is_valid():
                evidence = evidence_form.save(commit=False)
                evidence.dispute = dispute
                evidence.uploaded_by = request.user
                evidence.save()
                
                DisputeTimeline.objects.create(
                    dispute=dispute,
                    action_type='evidence_uploaded',
                    actor=request.user,
                    description=f"Evidence uploaded: {evidence.title}",
                    metadata={'evidence_id': str(evidence.id)}
                )
                
                messages.success(request, "Evidence uploaded successfully.")
                return redirect('orders:dispute_detail', dispute_id=dispute.id)
    
    return render(request, 'orders/dispute_detail.html', {
        'dispute': dispute,
        'messages': messages_list,
        'evidence': evidence_list,
        'timeline': timeline,
        'message_form': message_form,
        'evidence_form': evidence_form,
        'can_add_content': dispute.can_add_message(request.user) and dispute.status == 'open'
    })

@login_required
def user_disputes(request):
    """List user's disputes"""
    disputes = Dispute.objects.filter(
        Q(order__buyer=request.user) | Q(order__vendor=request.user)
    ).select_related('order', 'raised_by').order_by('-created_at')
    
    status_filter = request.GET.get('status')
    if status_filter:
        disputes = disputes.filter(status=status_filter)
    
    paginator = Paginator(disputes, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'orders/user_disputes.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'status_choices': Dispute.STATUS_CHOICES
    })

@login_required
def admin_dispute_resolution(request, dispute_id):
    """Admin interface for resolving disputes"""
    if not request.user.is_staff:
        raise Http404("Access denied")
    
    dispute = get_object_or_404(Dispute, id=dispute_id)
    
    if request.method == 'POST':
        form = AdminDisputeResolutionForm(request.POST, dispute=dispute)
        if form.is_valid():
            resolution_type = form.cleaned_data['resolution_type']
            resolution_notes = form.cleaned_data['resolution_notes']
            admin_notes = form.cleaned_data['admin_notes']
            refund_amount = form.cleaned_data.get('refund_amount')
            
            dispute.mark_resolved(
                resolution_type=resolution_type,
                resolved_by=request.user,
                notes=resolution_notes,
                refund_amount=refund_amount
            )
            
            if admin_notes:
                dispute.admin_notes = admin_notes
                dispute.save()
            
            DisputeMessage.objects.create(
                dispute=dispute,
                sender=request.user,
                message_type='admin',
                content=f"Dispute resolved: {resolution_notes}",
                is_internal=False
            )
            
            DisputeTimeline.objects.create(
                dispute=dispute,
                action_type='resolved',
                actor=request.user,
                description=f"Dispute resolved: {resolution_type}",
                metadata={
                    'resolution_type': resolution_type,
                    'refund_amount': str(refund_amount) if refund_amount else None
                }
            )
            
            messages.success(request, "Dispute has been resolved successfully.")
            return redirect('admin:dispute_detail', dispute_id=dispute.id)
    else:
        form = AdminDisputeResolutionForm(dispute=dispute)
    
    return render(request, 'admin/dispute_resolution.html', {
        'dispute': dispute,
        'form': form
    })

@login_required
def download_evidence(request, evidence_id):
    """Download dispute evidence file"""
    evidence = get_object_or_404(DisputeEvidence, id=evidence_id)
    
    if request.user not in evidence.dispute.get_participants() and not request.user.is_staff:
        raise Http404("Evidence not found")
    
    if not evidence.file:
        raise Http404("File not found")
    
    from django.http import FileResponse
    import os
    
    response = FileResponse(
        evidence.file.open('rb'),
        as_attachment=True,
        filename=os.path.basename(evidence.file.name)
    )
    
    return response

def dispute_statistics_api(request):
    """API endpoint for dispute statistics"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    from django.db.models import Count
    from datetime import timedelta
    
    now = timezone.now()
    last_30_days = now - timedelta(days=30)
    
    stats = {
        'total_disputes': Dispute.objects.count(),
        'open_disputes': Dispute.objects.filter(status='open').count(),
        'resolved_disputes': Dispute.objects.filter(status='resolved').count(),
        'disputes_last_30_days': Dispute.objects.filter(created_at__gte=last_30_days).count(),
        'dispute_types': list(
            Dispute.objects.values('dispute_type')
            .annotate(count=Count('dispute_type'))
            .order_by('-count')
        ),
        'resolution_types': list(
            Dispute.objects.filter(status='resolved')
            .values('resolution_type')
            .annotate(count=Count('resolution_type'))
            .order_by('-count')
        )
    }
    
    return JsonResponse(stats)
