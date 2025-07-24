from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages as django_messages
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from .models import Message
from accounts.models import User


@login_required
def message_list(request):
    messages = Message.objects.filter(
        Q(sender=request.user) | Q(recipient=request.user)
    ).select_related('sender', 'recipient').order_by('-created_at')
    
    conversations = {}
    for message in messages:
        if message.sender == request.user:
            other_user = message.recipient
        else:
            other_user = message.sender
            
        if not other_user:
            continue
            
        if other_user.id not in conversations:
            conversations[other_user.id] = {
                'other_user': other_user,
                'last_message': message,
                'messages': [],
                'unread_count': 0
            }
        
        conversations[other_user.id]['messages'].append(message)
        
        if message.recipient == request.user and not message.is_read:
            conversations[other_user.id]['unread_count'] += 1
    
    conversation_list = sorted(
        conversations.values(), 
        key=lambda x: x['last_message'].created_at, 
        reverse=True
    )
    
    return render(request, 'messaging/inbox.html', {
        'conversations': conversation_list,
        'total_messages': messages.count(),
        'messages': messages[:10]
    })


@login_required
def compose_message(request):
    if request.method == 'POST':
        recipient_username = request.POST.get('recipient', '').strip()
        subject = request.POST.get('subject', '').strip()
        content = request.POST.get('content', '').strip()
        encrypt = request.POST.get('encrypt') == 'on'
        
        if not recipient_username:
            django_messages.error(request, 'Please enter a recipient username')
            return render(request, 'messaging/compose.html', {
                'subject': subject,
                'content': content,
                'recipient_username': recipient_username
            })
        
        if not content:
            django_messages.error(request, 'Please enter a message')
            return render(request, 'messaging/compose.html', {
                'subject': subject,
                'content': content,
                'recipient_username': recipient_username
            })
        
        try:
            recipient = User.objects.get(username=recipient_username)
        except User.DoesNotExist:
            django_messages.error(request, f'User "{recipient_username}" not found')
            return render(request, 'messaging/compose.html', {
                'subject': subject,
                'content': content,
                'recipient_username': recipient_username
            })
        
        if recipient == request.user:
            django_messages.error(request, 'You cannot send a message to yourself')
            return render(request, 'messaging/compose.html', {
                'subject': subject,
                'content': content,
                'recipient_username': recipient_username
            })
        
        if not subject:
            subject = 'New Message'
        
        try:
            with transaction.atomic():
                message = Message.objects.create(
                    sender=request.user,
                    recipient=recipient,
                    subject=subject,
                    content=content,
                    created_at=timezone.now()
                )
                django_messages.success(request, 'Message sent successfully!')
                return redirect('messaging:detail', pk=message.pk)
        except Exception as e:
            django_messages.error(request, f'Error sending message: {str(e)}')
            return render(request, 'messaging/compose.html', {
                'subject': subject,
                'content': content,
                'recipient_username': recipient_username
            })
    
    recipient_username = request.GET.get('to', '')
    return render(request, 'messaging/compose.html', {
        'recipient_username': recipient_username
    })


@login_required
def conversation_view(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    
    messages = Message.objects.filter(
        Q(sender=request.user, recipient=other_user) | 
        Q(sender=other_user, recipient=request.user)
    ).order_by('created_at')
    
    unread_messages = messages.filter(recipient=request.user, is_read=False)
    unread_messages.update(is_read=True)
    
    all_messages = Message.objects.filter(
        Q(sender=request.user) | Q(recipient=request.user)
    ).select_related('sender', 'recipient').order_by('-created_at')
    
    conversations = {}
    for message in all_messages:
        if message.sender == request.user:
            conv_user = message.recipient
        else:
            conv_user = message.sender
            
        if not conv_user:
            continue
            
        if conv_user.id not in conversations:
            conversations[conv_user.id] = {
                'other_user': conv_user,
                'last_message': message,
                'messages': [],
                'unread_count': 0
            }
        
        conversations[conv_user.id]['messages'].append(message)
        
        if message.recipient == request.user and not message.is_read:
            conversations[conv_user.id]['unread_count'] += 1
    
    conversation_list = sorted(
        conversations.values(), 
        key=lambda x: x['last_message'].created_at, 
        reverse=True
    )
    
    current_conversation = {
        'other_user': other_user,
        'messages': messages
    }
    
    return render(request, 'messaging/inbox.html', {
        'conversations': conversation_list,
        'current_conversation': current_conversation,
        'total_messages': all_messages.count(),
    })


@login_required
def send_message(request, user_id):
    if request.method == 'POST':
        recipient = get_object_or_404(User, id=user_id)
        content = request.POST.get('content', '').strip()
        encrypt = request.POST.get('encrypt') == 'on'
        
        if not content:
            django_messages.error(request, 'Please enter a message')
            return redirect('messaging:conversation', user_id=user_id)
        
        if recipient == request.user:
            django_messages.error(request, 'You cannot send a message to yourself')
            return redirect('messaging:conversation', user_id=user_id)
        
        try:
            with transaction.atomic():
                message = Message.objects.create(
                    sender=request.user,
                    recipient=recipient,
                    subject='New Message',
                    content=content,
                    created_at=timezone.now()
                )
                django_messages.success(request, 'Message sent successfully!')
                return redirect('messaging:conversation', user_id=user_id)
        except Exception as e:
            django_messages.error(request, f'Error sending message: {str(e)}')
            return redirect('messaging:conversation', user_id=user_id)
    
    return redirect('messaging:list')


@login_required
def message_detail(request, pk):
    message = get_object_or_404(
        Message, 
        Q(sender=request.user) | Q(recipient=request.user),
        pk=pk
    )
    
    if message.recipient == request.user and not message.is_read:
        message.is_read = True
        message.save()
    
    return render(request, 'messaging/detail.html', {'message': message})


def check_new_messages(user):
    """Check if user has unread messages"""
    return Message.objects.filter(recipient=user, is_read=False).exists()


def get_unread_message_count(user):
    """Get count of unread messages for user"""
    return Message.objects.filter(recipient=user, is_read=False).count()
