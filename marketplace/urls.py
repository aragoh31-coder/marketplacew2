"""
URL configuration for marketplace project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from core.views import serve_secure_image
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
import os

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls', namespace='accounts')),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('products/', include('products.urls')),
    path('orders/', include('orders.urls')),
    path('wallets/', include('wallets.urls')),
    path('vendors/', include('vendors.urls')),
    path('messaging/', include('messaging.urls')),
    path('support/', include('support.urls')),
    path('adminpanel/', include('adminpanel.urls')),
    path('disputes/', include('disputes.urls')),
    path('security/', include('apps.security.urls')),
    path('anti_ddos/', include('apps.anti_ddos.urls')),
    
    path('secure-images/<path:path>', serve_secure_image, name='secure_image'),
    
    path('static/<path:path>', serve, {'document_root': settings.STATIC_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    for directory in settings.STATICFILES_DIRS:
        urlpatterns += static(settings.STATIC_URL, document_root=directory)
