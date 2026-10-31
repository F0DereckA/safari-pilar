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
    path('administrador/dashboard/exportar/', views.exportar_reporte_ventas, name='exportar_reporte_ventas'),
    path('mesero/', views.mesero, name='mesero'),
    path('cocina/', views.cocina, name='cocina'),
    path('cocina/cambiar-estado/', views.cambiar_estado_pedido, name='cambiar_estado_pedido'),
    path('ventas/<int:venta_id>/anular/', views.anular_venta, name='anular_venta'),
    path('administrador/backup/', views.administrador_backup, name='administrador_backup'),

    # Seguridad de Contrasenas y Expiracion Semestral (Tarea 1)
    path('cambiar-clave-expirada/', views.cambiar_clave_expirada, name='cambiar_clave_expirada'),

    # Verificacion QR, Cabanas y Descuentos Huespedes (Tarea 7)
    path('api/convenios/verificar/', views.api_verificar_convenio_qr, name='api_verificar_convenio_qr'),
    path('api/convenios/aplicar/', views.api_aplicar_consumo_convenio, name='api_aplicar_consumo_convenio'),
    path('administrador/convenios/', views.administrador_convenios, name='administrador_convenios'),
    path('administrador/ofertas-temporada/', views.administrador_ofertas_temporada, name='administrador_ofertas_temporada'),

    # Rutas de verificación para errores HTTP personalizados (Tarea 6)
    path('400/', views.error_400_view, name='error_400'),
    path('401/', views.error_401_view, name='error_401'),
    path('403/', views.error_403_view, name='error_403'),
    path('404/', views.error_404_view, name='error_404'),
    path('500/', views.error_500_view, name='error_500'),
    path('502/', views.error_502_view, name='error_502'),
    path('503/', views.error_503_view, name='error_503'),
    path('504/', views.error_504_view, name='error_504'),
]
