"""
URL configuration for Venta_safari project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('ventas.urls')),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.BASE_DIR / 'static'}),
]

# Manejadores de error HTTP personalizados (Semana 10)
handler400 = 'ventas.views.error_400_view'
handler403 = 'ventas.views.error_403_view'
handler404 = 'ventas.views.error_404_view'
handler500 = 'ventas.views.error_500_view'
