from django.http import HttpResponse, Http404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from django.conf import settings
import os
import mimetypes
from pathlib import Path

@cache_control(max_age=3600)  # Cache for 1 hour
def serve_secure_image(request, path):
    """
    Serve images from secure directory
    Only serves images, nothing else
    """
    if '..' in path or path.startswith('/'):
        raise Http404("Invalid path")
    
    full_path = settings.SECURE_UPLOAD_ROOT / path
    
    if not full_path.exists() or not full_path.is_file():
        raise Http404("Image not found")
    
    # Only serve .jpg files
    if not path.lower().endswith('.jpg'):
        raise Http404("Only JPEG images are served")
    
    try:
        with open(full_path, 'rb') as f:
            content = f.read()
        
        content_type = 'image/jpeg'
        
        response = HttpResponse(content, content_type=content_type)
        response['X-Content-Type-Options'] = 'nosniff'
        response['Content-Security-Policy'] = "default-src 'none'; img-src 'self';"
        
        return response
        
    except Exception:
        raise Http404("Error serving image")
