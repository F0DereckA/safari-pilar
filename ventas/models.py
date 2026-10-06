from django.db import models
from django.contrib.auth.models import User

# ==============================================================================
# 1. PERFIL DE EMPLEADO Y ROLES (RF01 - Autenticación y Perfiles)
# ==============================================================================
class PerfilEmpleado(models.Model):
    """Extensión de User para roles oficiales del Proyecto Integrado (Cajero, Administrador, Mesero)"""
    ROLES = [
        ('ADMINISTRADOR', 'Administrador'),
        ('CAJERO', 'Cajero'),
        ('MESERO', 'Mesero'),
    ]
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    rol = models.CharField(max_length=20, choices=ROLES, default='CAJERO')
    rut = models.CharField(max_length=12, blank=True, null=True, help_text="Formato: 12.345.678-9")
    telefono = models.CharField(max_length=20, blank=True, null=True)
    punto_venta_actual = models.ForeignKey(
        'PuntoVenta',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='empleados_asignados',
        help_text="Punto de venta o local actual asignado (solo uno por trabajador)"
    )
    activo = models.BooleanField(default=True)

    def __str__(self):
        nombre = self.usuario.get_full_name() or self.usuario.username
        local = f" - {self.punto_venta_actual.nombre}" if self.punto_venta_actual else " (Sin Local)"
        return f"{nombre} ({self.get_rol_display()}){local}"

    class Meta:
        verbose_name = "Perfil de Empleado"
        verbose_name_plural = "Perfiles de Empleados"


# ==============================================================================
# 2. JORNADA Y OPERACIÓN DIARIA (RF02 - Apertura/Cierre de Jornada)
# ==============================================================================
class Jornada(models.Model):
    """Representa el ciclo diario del parque; permite que el primer cajero o administrador abra la jornada"""
    ESTADOS = [
        ('ABIERTA', 'Abierta'),
        ('CERRADA', 'Cerrada'),
    ]
    fecha = models.DateField(auto_now_add=True)
    fecha_hora_apertura = models.DateTimeField(auto_now_add=True)
    fecha_hora_cierre = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=15, choices=ESTADOS, default='ABIERTA')
    usuario_apertura = models.ForeignKey(User, on_delete=models.PROTECT, related_name='jornadas_abiertas')
    usuario_cierre = models.ForeignKey(User, on_delete=models.PROTECT, related_name='jornadas_cerradas', null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Jornada #{self.id} ({self.fecha}) - {self.get_estado_display()}"

    class Meta:
        verbose_name = "Jornada"
        verbose_name_plural = "Jornadas"
        ordering = ['-fecha_hora_apertura']


# ==============================================================================
# 3. PUNTOS DE VENTA (RF03 - Locales / Restaurantes / Barras)
# ==============================================================================
class PuntoVenta(models.Model):
    """Locales o puntos de venta físicos dentro del parque (genérico, sin límite fijo de registros)"""
    nombre = models.CharField(max_length=100, unique=True)
    tipo = models.CharField(max_length=50, blank=True, null=True, help_text="Ej: Restaurante, Cafetería, Kiosco")
    descripcion = models.TextField(blank=True, null=True)
    icono = models.CharField(max_length=50, default='bi-shop', blank=True, help_text="Ícono Bootstrap")
    color = models.CharField(max_length=20, default='#c62828', blank=True, help_text="Color distintivo hex")
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Punto de Venta"
        verbose_name_plural = "Puntos de Venta"
        ordering = ['nombre']


# ==============================================================================
# 4. CAJAS POR TURNO (RF04 - Apertura y Cuadre de Caja Individual)
# ==============================================================================
class Caja(models.Model):
    """Caja individual asociada a un cajero, a un punto de venta y a una jornada operativa"""
    ESTADOS = [
        ('ABIERTA', 'Abierta'),
        ('CERRADA', 'Cerrada'),
    ]
    nombre = models.CharField(max_length=50, help_text="Ej: Caja 1, Terminal Mostrador")
    punto_venta = models.ForeignKey(PuntoVenta, on_delete=models.PROTECT, related_name='cajas')
    jornada = models.ForeignKey(Jornada, on_delete=models.PROTECT, related_name='cajas')
    cajero = models.ForeignKey(User, on_delete=models.PROTECT, related_name='cajas_asignadas')
    monto_apertura = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Fondo inicial de sencillo")
    monto_cierre = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fecha_hora_apertura = models.DateTimeField(auto_now_add=True)
    fecha_hora_cierre = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(max_length=15, choices=ESTADOS, default='ABIERTA')
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.nombre} - {self.punto_venta.nombre} [{self.get_estado_display()}]"

    class Meta:
        verbose_name = "Caja"
        verbose_name_plural = "Cajas"
        ordering = ['-fecha_hora_apertura']
        constraints = [
            models.UniqueConstraint(fields=['jornada', 'cajero'], name='unique_caja_por_cajero_jornada')
        ]


# ==============================================================================
# 5. CATEGORÍAS GASTRONÓMICAS
# ==============================================================================
class Categoria(models.Model):
    """Categorías de productos (Comida Preparada, Comida por Cocinar, Bebidas Envasadas, Cafetería)"""
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ['nombre']


# ==============================================================================
# 6. PRODUCTOS GASTRONÓMICOS
# ==============================================================================
class Producto(models.Model):
    """Alimentos y bebidas disponibles en el parque con precio base y disponibilidad por local"""
    nombre = models.CharField(max_length=150)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='productos')
    precio_base = models.DecimalField(max_digits=10, decimal_places=2)
    descripcion = models.TextField(blank=True, null=True)
    puntos_venta = models.ManyToManyField(PuntoVenta, blank=True, related_name='productos_disponibles')
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} (${self.precio_base:,.0f})"

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['categoria', 'nombre']


# ==============================================================================
# 7. MENÚ POR PUNTO DE VENTA (RF05 - Menú por local sin duplicar productos)
# ==============================================================================
class Menu(models.Model):
    """Menú asignado a un punto de venta que agrupa productos disponibles para la carta"""
    nombre = models.CharField(max_length=100)
    punto_venta = models.ForeignKey(PuntoVenta, on_delete=models.CASCADE, related_name='menus')
    productos = models.ManyToManyField(Producto, related_name='menus', blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre} ({self.punto_venta.nombre})"

    class Meta:
        verbose_name = "Menú"
        verbose_name_plural = "Menús"


# ==============================================================================
# 8. PRECIOS ESPECIALES (Estructura separada para promociones/convenios)
# ==============================================================================
class PrecioEspecial(models.Model):
    """Precios diferenciados para productos (ej. funcionarios, convenios institucionales o descuentos)"""
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='precios_especiales')
    nombre_condicion = models.CharField(max_length=100, help_text="Motivo o convenio")
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.producto.nombre} - ${self.precio:,.0f} ({self.nombre_condicion})"

    class Meta:
        verbose_name = "Precio Especial"
        verbose_name_plural = "Precios Especiales"


# ==============================================================================
# 9. MESAS (RF06 - Gestión y estado de mesas)
# ==============================================================================
class Mesa(models.Model):
    """Mesas de atención para comensales en restaurantes o terrazas"""
    ESTADOS = [
        ('HABILITADA', 'Habilitada / Libre'),
        ('OCUPADA', 'Ocupada'),
        ('RESERVADA', 'Reservada'),
        ('INACTIVA', 'Inactiva / Mantenimiento'),
    ]
    identificador = models.CharField(max_length=20, help_text="Ej: Mesa 1, Terraza 3")
    punto_venta = models.ForeignKey(PuntoVenta, on_delete=models.PROTECT, related_name='mesas')
    capacidad = models.PositiveIntegerField(default=4)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='HABILITADA')

    def __str__(self):
        return f"{self.identificador} ({self.punto_venta.nombre}) - {self.get_estado_display()}"

    class Meta:
        verbose_name = "Mesa"
        verbose_name_plural = "Mesas"
        unique_together = ('identificador', 'punto_venta')


# ==============================================================================
# 10. VENTAS (RF07/RF08 - Registro y Cobro de Ventas)
# ==============================================================================
class Venta(models.Model):
    """Venta gastronómica asociada a una caja, cajero y modalidad (Mesa o Venta Rápida)"""
    MODALIDADES = [
        ('VENTA_RAPIDA', 'Venta Rápida / Mostrador'),
        ('MESA', 'Consumo en Mesa'),
    ]
    METODOS_PAGO = [
        ('EFECTIVO', 'Efectivo'),
        ('DEBITO', 'Tarjeta Débito'),
        ('CREDITO', 'Tarjeta Crédito'),
        ('TRANSFERENCIA', 'Transferencia'),
    ]
    ESTADOS = [
        ('PAGADA', 'Pagada / Completada'),
        ('ANULADA', 'Anulada'),
    ]
    caja = models.ForeignKey(Caja, on_delete=models.PROTECT, related_name='ventas')
    cajero = models.ForeignKey(User, on_delete=models.PROTECT, related_name='ventas_realizadas')
    punto_venta = models.ForeignKey(PuntoVenta, on_delete=models.PROTECT, related_name='ventas')
    modalidad = models.CharField(max_length=20, choices=MODALIDADES, default='VENTA_RAPIDA')
    mesa = models.ForeignKey(Mesa, on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas')
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, default='EFECTIVO')
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PAGADA')
    fecha_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Venta #{self.id} (${self.total:,.0f}) - {self.get_modalidad_display()}"

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ['-fecha_hora']


# ==============================================================================
# 11. DETALLE DE VENTA
# ==============================================================================
class DetalleVenta(models.Model):
    """Línea de ítem vendido con producto, cantidad, precio aplicado y subtotal"""
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='detalles_venta')
    cantidad = models.PositiveIntegerField(default=1)
    precio_aplicado = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre} en Venta #{self.venta.id}"

    class Meta:
        verbose_name = "Detalle de Venta"
        verbose_name_plural = "Detalles de Venta"


# ==============================================================================
# 12. PEDIDOS / COMANDAS OPERATIVAS (RF09 - Derivación a Cocina y Barra)
# ==============================================================================
class Pedido(models.Model):
    """Comanda de producción gastronómica derivada de una venta"""
    ESTADOS = [
        ('PENDIENTE', 'Pendiente'),
        ('EN_PREPARACION', 'En Preparación'),
        ('LISTO', 'Listo para Entrega'),
        ('ENTREGADO', 'Entregado'),
        ('CANCELADO', 'Cancelado'),
    ]
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='pedidos')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')
    observaciones = models.TextField(blank=True, null=True, help_text="Instrucciones especiales para cocina/barra")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Pedido #{self.id} (Venta #{self.venta.id}) - {self.get_estado_display()}"

    class Meta:
        verbose_name = "Pedido / Comanda"
        verbose_name_plural = "Pedidos / Comandas"
        ordering = ['-creado_en']


# ==============================================================================
# 13. DETALLE DE PEDIDO
# ==============================================================================
class DetallePedido(models.Model):
    """Ítem específico del pedido con observaciones individuales"""
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='detalles_pedido')
    cantidad = models.PositiveIntegerField(default=1)
    observaciones = models.CharField(max_length=200, blank=True, null=True, help_text="Ej: sin sal, sin hielo, término medio")

    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre} (Pedido #{self.pedido.id})"

    class Meta:
        verbose_name = "Detalle de Pedido"
        verbose_name_plural = "Detalles de Pedido"


# ==============================================================================
# 14. TICKETS DE PRODUCCIÓN E IMPRESIÓN (RF10 - Tickets Cocina / Barra / Cliente)
# ==============================================================================
class Ticket(models.Model):
    """Ticket físico/virtual con destino operativo (Cocina, Barra o Comprobante)"""
    DESTINOS = [
        ('COCINA', 'Cocina Caliente'),
        ('BARRA', 'Barra / Cafetería'),
        ('COMPROBANTE', 'Comprobante de Cliente'),
    ]
    ESTADOS = [
        ('EMITIDO', 'Emitido'),
        ('EN_PROCESO', 'En Proceso'),
        ('FINALIZADO', 'Finalizado'),
    ]
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='tickets')
    codigo = models.CharField(max_length=30, unique=True, help_text="Ej: COM-0085, TIK-C-0102")
    tipo_destino = models.CharField(max_length=20, choices=DESTINOS, default='COCINA')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='EMITIDO')
    fecha_hora = models.DateTimeField(auto_now_add=True)
    contenido_impresion = models.TextField(blank=True, null=True, help_text="Texto listo para impresora térmica futura")

    def __str__(self):
        return f"Ticket #{self.codigo} [{self.get_tipo_destino_display()}] - {self.get_estado_display()}"

    class Meta:
        verbose_name = "Ticket de Producción"
        verbose_name_plural = "Tickets de Producción"
        ordering = ['-fecha_hora']


# ==============================================================================
# 15. ENTREGA DE PEDIDOS (RF11 - Medición de tiempos de entrega)
# ==============================================================================
class Entrega(models.Model):
    """Marca de tiempo de entrega final al comensal para auditoría de tiempos de servicio"""
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='entregas')
    ticket = models.ForeignKey(Ticket, on_delete=models.SET_NULL, null=True, blank=True, related_name='entregas')
    usuario_entrega = models.ForeignKey(User, on_delete=models.PROTECT, related_name='entregas_realizadas', null=True, blank=True)
    fecha_hora_entrega = models.DateTimeField(auto_now_add=True)
    observaciones = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f"Entrega Pedido #{self.pedido.id} ({self.fecha_hora_entrega.strftime('%H:%M:%S')})"

    class Meta:
        verbose_name = "Entrega de Pedido"
        verbose_name_plural = "Entregas de Pedidos"
        ordering = ['-fecha_hora_entrega']


# ==============================================================================
# 16. CONSUMO INTERNO DE TRABAJADORES (RF12 - Registro de Fiado / Consumo Personal)
# ==============================================================================
class ConsumoInterno(models.Model):
    """Registro de colaciones o consumos de colaboradores para descuento de personal"""
    ESTADOS = [
        ('REGISTRADO', 'Registrado / Pendiente Descuento'),
        ('DESCONTADO', 'Descontado por Planilla'),
        ('ANULADO', 'Anulado'),
    ]
    empleado = models.ForeignKey(User, on_delete=models.PROTECT, related_name='consumos_internos')
    punto_venta = models.ForeignKey(PuntoVenta, on_delete=models.PROTECT, related_name='consumos_internos')
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='REGISTRADO')
    fecha_hora = models.DateTimeField(auto_now_add=True)
    observaciones = models.TextField(blank=True, null=True)

    def __str__(self):
        nombre = self.empleado.get_full_name() or self.empleado.username
        return f"Consumo #{self.id} - {nombre} (${self.total:,.0f})"

    class Meta:
        verbose_name = "Consumo Interno"
        verbose_name_plural = "Consumos Internos"
        ordering = ['-fecha_hora']


# ==============================================================================
# 17. DETALLE DE CONSUMO INTERNO
# ==============================================================================
class DetalleConsumoInterno(models.Model):
    """Productos y cantidades consumidas por el colaborador"""
    consumo = models.ForeignKey(ConsumoInterno, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='detalles_consumo_interno')
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre} en Consumo #{self.consumo.id}"

    class Meta:
        verbose_name = "Detalle de Consumo Interno"
        verbose_name_plural = "Detalles de Consumos Internos"


# ==============================================================================
# 18. ALERTAS DE TRASLADO DE PERSONAL (Gestión y Auditoría de Trabajadores)
# ==============================================================================
class AlertaTraslado(models.Model):
    """Alerta generada cuando un trabajador es trasladado o reasignado a otro punto de venta"""
    empleado = models.ForeignKey(User, on_delete=models.CASCADE, related_name='alertas_traslado')
    punto_venta_origen = models.ForeignKey(PuntoVenta, on_delete=models.SET_NULL, null=True, blank=True, related_name='traslados_salientes')
    punto_venta_destino = models.ForeignKey(PuntoVenta, on_delete=models.CASCADE, related_name='traslados_entrantes')
    autorizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='traslados_autorizados')
    motivo = models.CharField(max_length=255, blank=True, null=True, default="Reasignación operativa de personal")
    fecha_hora = models.DateTimeField(auto_now_add=True)
    leida = models.BooleanField(default=False)

    def __str__(self):
        nombre = self.empleado.get_full_name() or self.empleado.username
        origen = self.punto_venta_origen.nombre if self.punto_venta_origen else "Sin Asignar"
        return f"Alerta Traslado: {nombre} ({origen} -> {self.punto_venta_destino.nombre})"

    class Meta:
        verbose_name = "Alerta de Traslado"
        verbose_name_plural = "Alertas de Traslado"
        ordering = ['-fecha_hora']

