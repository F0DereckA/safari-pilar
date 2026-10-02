from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('vendedor/', views.vendedor, name='vendedor'),
    path('vendedor/abrir-jornada/', views.abrir_jornada, name='abrir_jornada'),
    path('vendedor/abrir-caja/', views.abrir_caja, name='abrir_caja'),
    path('vendedor/crear-ticket/', views.crear_ticket, name='crear_ticket'),
    path('administrador/', views.administrador, name='administrador'),
    path('administrador/local/<int:local_id>/', views.administrador_local, name='administrador_local'),
    path('administrador/dashboard/', views.administrador_dashboard, name='administrador_dashboard'),
    path('administrador/trabajadores/', views.administrador_trabajadores, name='administrador_trabajadores'),
    path('mesero/', views.mesero, name='mesero'),
]
