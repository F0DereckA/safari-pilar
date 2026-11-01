from django.contrib import admin
from .models import (
    PerfilEmpleado, Jornada, PuntoVenta, Caja, Categoria, Producto,
    Menu, PrecioEspecial, Mesa, Venta, DetalleVenta, Pedido,
    DetallePedido, Ticket, Entrega, ConsumoInterno, DetalleConsumoInterno,
    AlertaTraslado, ReasignacionMesa, RegistroPrecioEspecial,
    PuntoImpresion, RegistroImpresion
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
    list_display = ('id', 'nombre', 'destino_defecto', 'activo')
    list_filter = ('destino_defecto', 'activo')
    search_fields = ('nombre',)

class PrecioEspecialInline(admin.TabularInline):
    model = PrecioEspecial
    extra = 1

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'categoria', 'precio_base', 'destino_operativo', 'activo')
    list_filter = ('categoria', 'destino_operativo', 'activo', 'puntos_venta')
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
    list_display = ('id', 'codigo', 'pedido', 'venta', 'tipo_destino', 'punto_venta', 'punto_impresion', 'estado_impresion', 'intentos_impresion', 'es_reimpresion', 'numero_reimpresiones', 'fecha_hora')
    list_filter = ('tipo_destino', 'estado', 'estado_impresion', 'es_reimpresion', 'punto_venta')
    search_fields = ('codigo', 'venta__id', 'error_impresion')

@admin.register(PuntoImpresion)
class PuntoImpresionAdmin(admin.ModelAdmin):
    list_display = ('id', 'nombre', 'punto_venta', 'tipo_destino', 'tipo_conexion', 'direccion_ip', 'puerto', 'estado_operativo', 'activo', 'simular_fallo')
    list_filter = ('tipo_destino', 'tipo_conexion', 'estado_operativo', 'activo', 'punto_venta')
    search_fields = ('nombre', 'direccion_ip')

@admin.register(RegistroImpresion)
class RegistroImpresionAdmin(admin.ModelAdmin):
    list_display = ('id', 'ticket', 'punto_impresion', 'exitoso', 'modo', 'es_reintento', 'usuario', 'fecha_hora')
    list_filter = ('exitoso', 'modo', 'es_reintento', 'fecha_hora')
    search_fields = ('ticket__codigo', 'mensaje_error')

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

@admin.register(ReasignacionMesa)
class ReasignacionMesaAdmin(admin.ModelAdmin):
    list_display = ('id', 'venta', 'mesa_origen', 'mesa_destino', 'mesero', 'motivo', 'fecha_hora')
    list_filter = ('mesa_origen__punto_venta', 'fecha_hora')
    search_fields = ('venta__id', 'mesa_origen__identificador', 'mesa_destino__identificador', 'mesero__username')

@admin.register(RegistroPrecioEspecial)
class RegistroPrecioEspecialAdmin(admin.ModelAdmin):
    list_display = ('id', 'venta', 'producto', 'precio_original', 'precio_aplicado', 'descuento_unitario', 'cantidad', 'usuario', 'motivo', 'fecha_hora')
    list_filter = ('motivo', 'fecha_hora', 'convenio_origen')
    search_fields = ('venta__id', 'producto__nombre', 'usuario__username', 'motivo')



