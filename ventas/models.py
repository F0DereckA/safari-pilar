from datetime import timedelta
from decimal import Decimal
from django.utils import timezone
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
        ('COCINERO', 'Cocinero'),
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
    # Seguridad de Contrasenas y Defensa contra Fuerza Bruta (ISO/IEC 27400 y Tarea 1)
    fecha_cambio_clave = models.DateTimeField(default=timezone.now, help_text="Fecha de ultima actualizacion de contrasena")
    dias_expiracion_clave = models.PositiveIntegerField(default=180, help_text="Vigencia maxima de clave en dias (180 dias = 6 meses)")
    intentos_fallidos = models.PositiveIntegerField(default=0, help_text="Contador de intentos fallidos consecutivos")
    bloqueado_hasta = models.DateTimeField(null=True, blank=True, help_text="Fecha y hora hasta cuando el acceso esta bloqueado")

    def clave_expirada(self):
        """Verifica si han transcurrido 6 meses (180 dias) desde el ultimo cambio de contrasena"""
        if not self.fecha_cambio_clave:
            return False
        return (timezone.now() - self.fecha_cambio_clave).days >= self.dias_expiracion_clave

    def esta_bloqueado(self):
        """Determina si la cuenta esta temporalmente bloqueada por acumulacion de intentos fallidos"""
        if self.bloqueado_hasta and self.bloqueado_hasta > timezone.now():
            return True
        return False

    def registrar_intento_fallido(self, max_intentos=5, minutos_bloqueo=5):
        """Registra un intento fallido y bloquea la cuenta si supera el umbral"""
        self.intentos_fallidos += 1
        if self.intentos_fallidos >= max_intentos:
            self.bloqueado_hasta = timezone.now() + timedelta(minutes=minutos_bloqueo)
            self.intentos_fallidos = 0
        self.save(update_fields=['intentos_fallidos', 'bloqueado_hasta'])

    def limpiar_intentos_fallidos(self):
        """Restaura los intentos fallidos tras un login exitoso"""
        if self.intentos_fallidos > 0 or self.bloqueado_hasta is not None:
            self.intentos_fallidos = 0
            self.bloqueado_hasta = None
            self.save(update_fields=['intentos_fallidos', 'bloqueado_hasta'])

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

    # ==========================================================================
    # Subproceso de Cuadratura y Arqueo por Denominación (Semana 12 / Ley 20.956)
    # ==========================================================================
    billetes_20000 = models.PositiveIntegerField(default=0, help_text="Billetes $20.000")
    billetes_10000 = models.PositiveIntegerField(default=0, help_text="Billetes $10.000")
    billetes_5000 = models.PositiveIntegerField(default=0, help_text="Billetes $5.000")
    billetes_2000 = models.PositiveIntegerField(default=0, help_text="Billetes $2.000")
    billetes_1000 = models.PositiveIntegerField(default=0, help_text="Billetes $1.000")

    monedas_500 = models.PositiveIntegerField(default=0, help_text="Monedas $500")
    monedas_100 = models.PositiveIntegerField(default=0, help_text="Monedas $100")
    monedas_50 = models.PositiveIntegerField(default=0, help_text="Monedas $50")
    monedas_10 = models.PositiveIntegerField(default=0, help_text="Monedas $10")
    monedas_5 = models.PositiveIntegerField(default=0, help_text="Monedas $5 (Pauta / Ley 20.956)")
    monedas_1 = models.PositiveIntegerField(default=0, help_text="Monedas $1 (Pauta / Ley 20.956)")

    total_efectivo_declarado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_efectivo_esperado = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    diferencia_cuadre = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    ESTADOS_CUADRE = [
        ('PENDIENTE', 'Pendiente de Cierre'),
        ('CUADRADA', 'Cuadrada Exacta'),
        ('SOBRANTE', 'Sobrante en Caja'),
        ('FALTANTE', 'Faltante en Caja'),
    ]
    estado_cuadre = models.CharField(max_length=20, choices=ESTADOS_CUADRE, default='PENDIENTE')

    def calcular_total_arqueo(self):
        """Calcula el total físico contado por el cajero"""
        return (
            self.billetes_20000 * 20000 +
            self.billetes_10000 * 10000 +
            self.billetes_5000 * 5000 +
            self.billetes_2000 * 2000 +
            self.billetes_1000 * 1000 +
            self.monedas_500 * 500 +
            self.monedas_100 * 100 +
            self.monedas_50 * 50 +
            self.monedas_10 * 10 +
            self.monedas_5 * 5 +
            self.monedas_1 * 1
        )

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
    """Alimentos y bebidas disponibles en el parque con precio base, disponibilidad por local y motor de promociones por volumen"""
    TIPOS_OFERTA = [
        ('NINGUNA', 'Sin Oferta'),
        ('3X2', 'Lleva 3 y Paga 2 (3x2)'),
        ('2X1', 'Lleva 2 y Paga 1 (2x1)'),
        ('SEGUNDA_1', 'Segunda Unidad a $1 peso'),
        ('PRECIO_FIJO', 'Precio de Oferta Fijo'),
        ('DESCUENTO_PCT', 'Descuento Porcentual'),
    ]

    nombre = models.CharField(max_length=150)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='productos')
    precio_base = models.DecimalField(max_digits=10, decimal_places=2)
    descripcion = models.TextField(blank=True, null=True)
    puntos_venta = models.ManyToManyField(PuntoVenta, blank=True, related_name='productos_disponibles')
    activo = models.BooleanField(default=True)
    en_oferta = models.BooleanField(default=False, help_text="Indica si el producto tiene promoción u oferta activa")
    tipo_oferta = models.CharField(max_length=20, choices=TIPOS_OFERTA, default='NINGUNA', help_text="Tipo de promoción (3x2, 2da a $1 peso, etc.)")
    precio_oferta = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Precio promocional fijo o precio de la 2da unidad (ej. $1)")
    descuento_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Porcentaje de descuento para tipo DESCUENTO_PCT")
    descripcion_oferta = models.CharField(max_length=120, blank=True, null=True, help_text="Etiqueta visible: Ej: ¡Lleva 3 y paga 2!, ¡Segunda hamburguesa a $1!")
    creado_en = models.DateTimeField(auto_now_add=True)

    @property
    def precio_actual(self):
        """Retorna el precio unitario base o el precio de oferta fijo si aplica"""
        if self.en_oferta and self.tipo_oferta in ['PRECIO_FIJO', 'NINGUNA'] and self.precio_oferta is not None and self.precio_oferta > 0:
            return self.precio_oferta
        return self.precio_base

    def calcular_total_promocion(self, cantidad):
        """
        Calcula el total a cobrar aplicando la promoción de volumen/oferta:
        - 3x2: Cada grupo de 3 paga 2 (1 gratis)
        - 2x1: Cada grupo de 2 paga 1
        - SEGUNDA_1: Cada par paga 1 precio base + 1 peso (o precio_oferta)
        - PRECIO_FIJO: cantidad * precio_oferta
        - DESCUENTO_PCT: cantidad * (precio_base * (1 - pct/100))
        Retorna: (total_a_cobrar, ahorro, texto_detalle)
        """
        cant = max(1, int(cantidad))
        p_base = self.precio_base
        total_sin_promo = cant * p_base

        if not self.en_oferta or self.tipo_oferta == 'NINGUNA':
            return total_sin_promo, Decimal('0'), ""

        if self.tipo_oferta == '3X2':
            grupos_3 = cant // 3
            resto = cant % 3
            unidades_a_cobrar = (grupos_3 * 2) + resto
            total = unidades_a_cobrar * p_base
            ahorro = total_sin_promo - total
            texto = f"Promo 3x2 aplicada ({grupos_3} gratis)" if grupos_3 > 0 else "Promo 3x2 activa"
            return total, ahorro, texto

        elif self.tipo_oferta == '2X1':
            grupos_2 = cant // 2
            resto = cant % 2
            unidades_a_cobrar = grupos_2 + resto
            total = unidades_a_cobrar * p_base
            ahorro = total_sin_promo - total
            texto = f"Promo 2x1 aplicada ({grupos_2} gratis)" if grupos_2 > 0 else "Promo 2x1 activa"
            return total, ahorro, texto

        elif self.tipo_oferta == 'SEGUNDA_1':
            precio_segunda = self.precio_oferta if (self.precio_oferta is not None and self.precio_oferta > 0) else Decimal('1')
            pares = cant // 2
            sobrante = cant % 2
            # Cada par paga 1 al precio base y 1 a $1 peso
            total = (pares * (p_base + precio_segunda)) + (sobrante * p_base)
            ahorro = total_sin_promo - total
            texto = f"Promo 2da unidad a ${precio_segunda:,.0f} aplicada" if pares > 0 else "Lleva 2da a $1 peso"
            return total, ahorro, texto

        elif self.tipo_oferta == 'PRECIO_FIJO' and self.precio_oferta is not None and self.precio_oferta > 0:
            total = cant * self.precio_oferta
            ahorro = max(Decimal('0'), total_sin_promo - total)
            texto = f"Precio Oferta: ${self.precio_oferta:,.0f}"
            return total, ahorro, texto

        elif self.tipo_oferta == 'DESCUENTO_PCT' and self.descuento_pct > 0:
            factor = (Decimal('100') - self.descuento_pct) / Decimal('100')
            total = cant * (p_base * factor)
            ahorro = total_sin_promo - total
            texto = f"{self.descuento_pct}% Descuento"
            return total, ahorro, texto

        return total_sin_promo, Decimal('0'), ""

    def __str__(self):
        if self.en_oferta:
            return f"{self.nombre} [OFERTA {self.get_tipo_oferta_display()}] (${self.precio_base:,.0f})"
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
        ('ABIERTA', 'Abierta / En Consumo'),
        ('PAGADA', 'Pagada / Completada'),
        ('ANULADA', 'Anulada'),
    ]
    caja = models.ForeignKey(Caja, on_delete=models.PROTECT, related_name='ventas')
    cajero = models.ForeignKey(User, on_delete=models.PROTECT, related_name='ventas_realizadas')
    punto_venta = models.ForeignKey(PuntoVenta, on_delete=models.PROTECT, related_name='ventas')
    modalidad = models.CharField(max_length=20, choices=MODALIDADES, default='VENTA_RAPIDA')
    mesa = models.ForeignKey(Mesa, on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas')
    metodo_pago = models.CharField(max_length=20, choices=METODOS_PAGO, default='EFECTIVO')
    total_sin_redondeo = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Monto antes de redondeo de ley")
    redondeo_ley_20956 = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Ajuste Ley 20.956 para efectivo")
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

# ==============================================================================
# 19. CONVENIOS Y PASES HUESPEDES (CABANAS, DESAYUNO INCLUIDO Y DESCUENTOS QR)
# ==============================================================================
class ConvenioHuesped(models.Model):
    """Pases y convenios para visitantes y huespedes de cabanas de Parque Safari (RF13 / Tarea 7)"""
    TIPOS_BENEFICIO = [
        ('DESAYUNO_INCLUIDO', 'Desayuno Incluido (100% Bonificado)'),
        ('DESCUENTO_PORCENTAJE', 'Descuento Porcentual'),
        ('DESCUENTO_MONTO', 'Descuento Monto Fijo ($)'),
    ]
    codigo_qr = models.CharField(max_length=64, unique=True, db_index=True, help_text="Codigo unico de barra o QR")
    numero_cabana = models.CharField(max_length=50, help_text="Ej: Cabana 12, Suite Los Leones")
    nombre_titular = models.CharField(max_length=150, help_text="Nombre del huesped o titular de la reserva")
    rut_titular = models.CharField(max_length=15, blank=True, null=True, help_text="RUT o pasaporte")
    tipo_beneficio = models.CharField(max_length=30, choices=TIPOS_BENEFICIO, default='DESAYUNO_INCLUIDO')
    valor_descuento = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('100.00'), help_text="100 para desayuno total, % descuento o monto en pesos")
    limite_diario = models.PositiveIntegerField(default=1, help_text="Numero maximo de consumos bonificados por dia")
    fecha_checkin = models.DateField(default=timezone.now)
    fecha_checkout = models.DateField()
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    def es_valido_hoy(self):
        """Verifica que el pase este activo y dentro de las fechas de estadia"""
        hoy = timezone.now().date()
        return self.activo and (self.fecha_checkin <= hoy <= self.fecha_checkout)

    def consumos_hoy_count(self):
        """Calcula cuantas veces ha utilizado el beneficio durante la jornada de hoy"""
        hoy = timezone.now().date()
        return self.consumos.filter(fecha_hora__date=hoy).count()

    def puede_consumir_hoy(self):
        """Valida si aun le quedan consumos disponibles hoy"""
        return self.es_valido_hoy() and (self.consumos_hoy_count() < self.limite_diario)

    def __str__(self):
        return f"{self.numero_cabana} - {self.nombre_titular} [{self.codigo_qr}] ({self.get_tipo_beneficio_display()})"

    class Meta:
        verbose_name = "Convenio / Pase Huesped"
        verbose_name_plural = "Convenios / Pases Huespedes"
        ordering = ['-creado_en']


# ==============================================================================
# 20. REGISTRO DE CONSUMOS DE HUESPEDES (Auditoria y Trazabilidad)
# ==============================================================================
class ConsumoHuesped(models.Model):
    """Anotacion detallada de consumos de desayunos y descuentos aplicados a huespedes de cabanas"""
    convenio = models.ForeignKey(ConvenioHuesped, on_delete=models.CASCADE, related_name='consumos')
    ticket = models.ForeignKey('Ticket', on_delete=models.SET_NULL, null=True, blank=True, related_name='consumos_huesped')
    venta = models.ForeignKey('Venta', on_delete=models.SET_NULL, null=True, blank=True, related_name='consumos_huesped')
    monto_original = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    monto_bonificado = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    monto_pagado = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    fecha_hora = models.DateTimeField(auto_now_add=True)
    registrado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='consumos_huesped_registrados')
    observaciones = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Consumo {self.convenio.numero_cabana} - Bonificado: ${self.monto_bonificado:,.0f} ({self.fecha_hora.strftime('%d/%m/%Y %H:%M')})"

    class Meta:
        verbose_name = "Consumo de Huesped"
        verbose_name_plural = "Consumos de Huespedes"
        ordering = ['-fecha_hora']


# ==============================================================================
# 21. OFERTAS DE TEMPORADA (Activacion / Desactivacion por Administrador)
# ==============================================================================
class OfertaTemporada(models.Model):
    """Campanas y ofertas de temporada gestionadas por el Administrador"""
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True, null=True)
    descuento_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), help_text="Porcentaje de descuento global (0 - 100)")
    fecha_inicio = models.DateField(default=timezone.now)
    fecha_fin = models.DateField()
    activa = models.BooleanField(default=False, help_text="Interruptor maestro de activacion")
    categoria_aplicable = models.ForeignKey('Categoria', on_delete=models.SET_NULL, null=True, blank=True, related_name='ofertas_temporada', help_text="Categoria especifica o en blanco para toda la carta")
    creada_en = models.DateTimeField(auto_now_add=True)

    def es_vigente(self):
        hoy = timezone.now().date()
        return self.activa and (self.fecha_inicio <= hoy <= self.fecha_fin)

    def __str__(self):
        estado = "ACTIVA" if self.activa else "INACTIVA"
        return f"{self.nombre} ({self.descuento_porcentaje}%) [{estado}]"

    class Meta:
        verbose_name = "Oferta de Temporada"
        verbose_name_plural = "Ofertas de Temporada"
        ordering = ['-fecha_inicio']

