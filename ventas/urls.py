from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('vendedor/', views.vendedor, name='vendedor'),
    path('vendedor/abrir-jornada/', views.abrir_jornada, name='abrir_jornada'),
    path('vendedor/abrir-caja/', views.abrir_caja, name='abrir_caja'),
    path('vendedor/cerrar-caja/', views.cerrar_caja, name='cerrar_caja'),
    path('vendedor/crear-ticket/', views.crear_ticket, name='crear_ticket'),
    path('administrador/gestion/', views.administrador_gestion, name='administrador_gestion'),
    path('administrador/', views.administrador, name='administrador'),
    path('administrador/cerrar-jornada/', views.cerrar_jornada, name='cerrar_jornada'),
    path('administrador/local/<int:local_id>/', views.administrador_local, name='administrador_local'),
    path('administrador/trabajadores/', views.administrador_trabajadores, name='administrador_trabajadores'),
    path('administrador/mesas/', views.administrador_mesas, name='administrador_mesas'),
    path('administrador/productos/', views.administrador_productos, name='administrador_productos'),
    path('administrador/menus/', views.administrador_menus, name='administrador_menus'),
    path('administrador/historial/', views.administrador_historial, name='administrador_historial'),
    path('administrador/dashboard/', views.administrador_dashboard, name='administrador_dashboard'),
    path('mesero/', views.mesero, name='mesero'),
    path('cocina/', views.cocina, name='cocina'),
    path('cocina/cambiar-estado/', views.cambiar_estado_pedido, name='cambiar_estado_pedido'),
    path('ventas/<int:venta_id>/anular/', views.anular_venta, name='anular_venta'),
    path('administrador/backup/', views.administrador_backup, name='administrador_backup'),

    # Rutas de prueba/auditoría para errores HTTP personalizados (Semana 10)
    path('400/', views.error_400_view, name='error_400'),
    path('403/', views.error_403_view, name='error_403'),
    path('404/', views.error_404_view, name='error_404'),
    path('500/', views.error_500_view, name='error_500'),
]
