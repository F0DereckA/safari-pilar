from django.contrib import admin
from .models import (
    PerfilEmpleado, Jornada, PuntoVenta, Caja, Categoria, Producto,
    Menu, PrecioEspecial, Mesa, Venta, DetalleVenta, Pedido,
    DetallePedido, Ticket, Entrega, ConsumoInterno, DetalleConsumoInterno,
    AlertaTraslado
)

@admin.register(PerfilEmpleado)
class PerfilEmpleadoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'rol', 'rut', 'telefono', 'punto_venta_actual', 'activo')
    list_filter = ('rol', 'punto_venta_actual', 'activo')
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name', 'rut')

@admin.register(Jornada)
class JornadaAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha', 'estado', 'usuario_apertura', 'usuario_cierre', 'fecha_hora_apertura', 'fecha_hora_cierre')
    list_filter = ('estado', 'fecha')
    search_fields = ('observaciones',)

@admin.register(PuntoVenta)
class PuntoVentaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'tipo', 'activo', 'creado_en')
    list_filter = ('tipo', 'activo')
    search_fields = ('nombre', 'descripcion')

@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'punto_venta', 'cajero', 'estado', 'monto_apertura', 'monto_cierre', 'fecha_hora_apertura')
    list_filter = ('estado', 'punto_venta')
    search_fields = ('nombre', 'cajero__username')

@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'activo')
    list_filter = ('activo',)
    search_fields = ('nombre',)

class PrecioEspecialInline(admin.TabularInline):
    model = PrecioEspecial
    extra = 1

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'categoria', 'precio_base', 'activo')
    list_filter = ('categoria', 'activo', 'puntos_venta')
    search_fields = ('nombre', 'descripcion')
    filter_horizontal = ('puntos_venta',)
    inlines = [PrecioEspecialInline]

@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'punto_venta', 'activo')
    list_filter = ('punto_venta', 'activo')
    search_fields = ('nombre',)
    filter_horizontal = ('productos',)

@admin.register(PrecioEspecial)
class PrecioEspecialAdmin(admin.ModelAdmin):
    list_display = ('id', 'producto', 'nombre_condicion', 'precio', 'activo', 'fecha_inicio', 'fecha_fin')
    list_filter = ('activo',)
    search_fields = ('producto__nombre', 'nombre_condicion')

@admin.register(Mesa)
class MesaAdmin(admin.ModelAdmin):
    list_display = ('id', 'identificador', 'punto_venta', 'capacidad', 'estado')
    list_filter = ('punto_venta', 'estado')
    search_fields = ('identificador',)

class DetalleVentaInline(admin.TabularInline):
    model = DetalleVenta
    extra = 0

@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_hora', 'punto_venta', 'cajero', 'modalidad', 'mesa', 'metodo_pago', 'total', 'estado')
    list_filter = ('modalidad', 'metodo_pago', 'estado', 'punto_venta')
    search_fields = ('id', 'cajero__username')
    inlines = [DetalleVentaInline]

class DetallePedidoInline(admin.TabularInline):
    model = DetallePedido
    extra = 0

class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 0

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'venta', 'estado', 'creado_en', 'actualizado_en')
    list_filter = ('estado',)
    search_fields = ('id', 'observaciones')
    inlines = [DetallePedidoInline, TicketInline]

@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'codigo', 'pedido', 'tipo_destino', 'estado', 'fecha_hora')
    list_filter = ('tipo_destino', 'estado')
    search_fields = ('codigo',)

@admin.register(Entrega)
class EntregaAdmin(admin.ModelAdmin):
    list_display = ('id', 'pedido', 'ticket', 'usuario_entrega', 'fecha_hora_entrega')
    list_filter = ('fecha_hora_entrega',)
    search_fields = ('observaciones',)

class DetalleConsumoInternoInline(admin.TabularInline):
    model = DetalleConsumoInterno
    extra = 1

@admin.register(ConsumoInterno)
class ConsumoInternoAdmin(admin.ModelAdmin):
    list_display = ('id', 'empleado', 'punto_venta', 'total', 'estado', 'fecha_hora')
    list_filter = ('estado', 'punto_venta')
    search_fields = ('empleado__username', 'empleado__first_name', 'empleado__last_name')
    inlines = [DetalleConsumoInternoInline]

@admin.register(AlertaTraslado)
class AlertaTrasladoAdmin(admin.ModelAdmin):
    list_display = ('id', 'empleado', 'punto_venta_origen', 'punto_venta_destino', 'motivo', 'fecha_hora', 'leida')
    list_filter = ('punto_venta_origen', 'punto_venta_destino', 'leida')
    search_fields = ('empleado__username', 'empleado__first_name', 'empleado__last_name', 'motivo')

