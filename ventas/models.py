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
    debe_cambiar_clave = models.BooleanField(default=True, help_text="Exige cambio forzoso de contrasena en primer ingreso")
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

    def total_fiado_pendiente(self):
        """Calcula el total acumulado pendiente de descuento por planilla (RF10.3)"""
        from django.db.models import Sum
        from decimal import Decimal
        res = self.usuario.consumos_internos.filter(estado='REGISTRADO').aggregate(total=Sum('total'))['total']
        return res or Decimal('0.00')

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

    def tiene_cajas_abiertas(self):
        """Indica si el local tiene alguna caja operativa en estado ABIERTA (RF14)"""
        return self.cajas.filter(estado='ABIERTA').exists()

    def tiene_ventas_abiertas(self):
        """Indica si el local tiene alguna comanda o cuenta en salón en estado ABIERTA (RF14)"""
        return self.ventas.filter(estado='ABIERTA').exists()

    def tiene_historial_operativo(self):
        """Indica si el local tiene transacciones históricas que exigen soft-delete para auditoría (RF14)"""
        return (
            self.ventas.exists() or
            self.cajas.exists() or
            self.consumos_internos.exists() or
            self.mesas.filter(ventas__isnull=False).exists()
        )

    def get_productos_disponibles(self):
        """
        Retorna el QuerySet de productos activos habilitados para este punto de venta (RF15),
        combinando los asignados directamente y los presentes en sus menús activos.
        """
        from django.db.models import Q
        ProductoModel = self.productos_disponibles.model
        return ProductoModel.objects.filter(
            activo=True
        ).filter(
            Q(puntos_venta=self) | Q(menus__punto_venta=self, menus__activo=True)
        ).distinct()

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
    DESTINOS = [
        ('COCINA', 'Cocina Caliente / Elaboración'),
        ('BARRA', 'Barra / Cafetería / Snacks'),
    ]
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    destino_defecto = models.CharField(max_length=20, choices=DESTINOS, default='COCINA', help_text="Destino operativo por defecto para productos de esta categoría (RF08)")
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
    destino_operativo = models.CharField(
        max_length=20,
        choices=[
            ('COCINA', 'Cocina Caliente / Elaboración'),
            ('BARRA', 'Barra / Cafetería / Bebidas / Snacks'),
            ('COMPROBANTE', 'Solo Comprobante'),
        ],
        default='COCINA',
        help_text="Destino operativo del producto para despacho y tickets de comanda (RF08.1)"
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    def get_destino_operativo(self):
        """Determina el destino operativo real gobernado por la BD (RF08.1)"""
        nom = (self.nombre or '').lower()
        if any(k in nom for k in ['coca', 'sprite', 'fanta', 'bebida', 'jugo', 'café', 'cafe', 'té', 'infus', 'agua', 'moka', 'espresso', 'cappuccino', 'croissant', 'torta', 'snack']):
            return 'BARRA'
        if self.destino_operativo and self.destino_operativo in ['COCINA', 'BARRA']:
            return self.destino_operativo
        if self.categoria and hasattr(self.categoria, 'destino_defecto') and self.categoria.destino_defecto:
            return self.categoria.destino_defecto
        cat_nom = (self.categoria.nombre if self.categoria else '').lower()
        if any(k in cat_nom for k in ['cafeter', 'barra', 'jugo', 'bebida', 'snack', 'envasada']):
            return 'BARRA'
        return 'COCINA'

    def esta_disponible_en(self, punto_venta):
        """
        Indica si el producto está activo y habilitado para comercialización
        en el punto de venta especificado (RF15).
        """
        if not self.activo:
            return False
        if not punto_venta:
            return True
        return (
            self.puntos_venta.filter(id=punto_venta.id).exists() or
            self.menus.filter(punto_venta=punto_venta, activo=True).exists()
        )

    def to_mesero_dict(self):
        """
        Serializa el producto al formato esperado por la interfaz táctil de meseros (RF15),
        eliminando datos hardcodeados y gobernando la información desde la base de datos real.
        """
        destino = self.get_destino_operativo()
        if destino == 'COCINA':
            destino_badge = 'Impresora Cocina'
            categoria_slug = 'cocinar'
        elif destino == 'BARRA':
            destino_badge = 'Impresora Barra'
            nom_lower = (self.nombre or '').lower()
            cat_lower = (self.categoria.nombre if self.categoria else '').lower()
            if any(k in nom_lower or k in cat_lower for k in ['café', 'cafe', 'té', 'te', 'cappuccino', 'jugo', 'frutilla', 'naranja', 'limonada', 'infus']):
                categoria_slug = 'cafeteria'
            else:
                categoria_slug = 'envasada'
        else:
            destino_badge = 'Despacho Inmediato'
            categoria_slug = 'preparada'

        return {
            "id": self.id,
            "nombre": self.nombre,
            "categoria": categoria_slug,
            "categoria_nombre": self.categoria.nombre if self.categoria else "General",
            "destino": destino,
            "destino_badge": destino_badge,
            "precio": int(self.precio_actual),
            "precio_base": int(self.precio_base),
            "en_oferta": self.en_oferta,
            "descripcion_oferta": self.descripcion_oferta or '',
            "descripcion": self.descripcion or '',
        }

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

    def productos_activos(self):
        """Retorna únicamente los productos activos vinculados a este menú (RF15)"""
        return self.productos.filter(activo=True)

    def esta_vacio(self):
        """Indica si el menú no posee productos activos asignados (RF15)"""
        return not self.productos_activos().exists()

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
    codigo_convenio = models.CharField(max_length=50, blank=True, null=True, db_index=True, help_text="Código alfanumérico o QR de convenio institucional (RF07)")
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    def es_vigente(self, fecha=None):
        """Valida si el convenio o precio especial se encuentra activo y dentro del rango de fechas (RF07)"""
        if not self.activo:
            return False
        if not fecha:
            from django.utils import timezone
            fecha = timezone.localdate()
        if self.fecha_inicio and fecha < self.fecha_inicio:
            return False
        if self.fecha_fin and fecha > self.fecha_fin:
            return False
        return True

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
    fecha_ocupacion = models.DateTimeField(null=True, blank=True, help_text="Timestamp de inicio de ocupación actual de la mesa (RF17)")

    def get_venta_activa(self):
        """Retorna la cuenta abierta activa en esta mesa o None (RF17)"""
        if not self.pk:
            return None
        return self.ventas.filter(estado='ABIERTA').first()

    def get_inicio_ocupacion(self):
        """
        Retorna el timestamp de inicio de ocupación de la mesa (RF17).
        Prioriza fecha_ocupacion explícita; si no está definida pero existe cuenta abierta,
        utiliza fecha_hora de la Venta abierta (100% reconstruible desde BD).
        """
        if self.fecha_ocupacion:
            return self.fecha_ocupacion
        va = self.get_venta_activa()
        if va and va.fecha_hora:
            return va.fecha_hora
        return None

    def esta_ocupada(self):
        """Indica si la mesa está actualmente ocupada o con comanda/cuenta abierta (RF17)"""
        return self.estado == 'OCUPADA' or self.get_venta_activa() is not None

    def esta_disponible(self):
        """Indica si la mesa está formalmente habilitada y libre para nuevos comensales (RF17)"""
        return self.estado == 'HABILITADA' and not self.esta_ocupada()

    def get_duracion_ocupacion_minutos(self, ahora=None):
        """
        Retorna los minutos transcurridos desde el inicio de ocupación hasta ahora (RF17).
        Retorna None si la mesa no está ocupada. Nunca retorna valores negativos.
        """
        if not self.esta_ocupada():
            return None
        inicio = self.get_inicio_ocupacion()
        if not inicio:
            return None
        ahora = ahora or timezone.now()
        if timezone.is_naive(ahora) and timezone.is_aware(inicio):
            ahora = timezone.make_aware(ahora, timezone.get_current_timezone())
        elif timezone.is_aware(ahora) and timezone.is_naive(inicio):
            inicio = timezone.make_aware(inicio, timezone.get_current_timezone())
        delta = ahora - inicio
        return max(0.0, round(delta.total_seconds() / 60.0, 1))

    def get_duracion_ocupacion_segundos(self, ahora=None):
        """Retorna los segundos transcurridos de ocupación actual (RF17)"""
        minutos = self.get_duracion_ocupacion_minutos(ahora=ahora)
        return int(minutos * 60) if minutos is not None else None

    def ocupar(self, timestamp=None, guardar=True):
        """
        Marca la mesa como ocupada registrando el inicio de ocupación (RF17).
        Lanza ValidationError si la mesa está INACTIVA o ya se encuentra ocupada.
        """
        from django.core.exceptions import ValidationError
        if self.estado == 'INACTIVA':
            raise ValidationError(f"La mesa {self.identificador} está inactiva o en mantenimiento y no puede ser ocupada (RF17).")
        if self.estado == 'OCUPADA' and self.fecha_ocupacion is not None:
            raise ValidationError(f"La mesa {self.identificador} ya se encuentra ocupada.")
        self.estado = 'OCUPADA'
        self.fecha_ocupacion = timestamp or timezone.now()
        if guardar and self.pk:
            self.save(update_fields=['estado', 'fecha_ocupacion'])
        return self

    def liberar(self, forzar=False, guardar=True):
        """
        Libera la mesa marcándola como HABILITADA y reseteando fecha_ocupacion (RF17).
        Si forzar=False y existe una cuenta abierta pendiente, lanza ValidationError (blindaje contra liberar con cuenta abierta).
        """
        from django.core.exceptions import ValidationError
        if not forzar:
            va = self.get_venta_activa()
            if va is not None:
                raise ValidationError(
                    f"No se puede liberar la mesa {self.identificador} porque tiene la cuenta abierta #{va.id} pendiente de cobro (RF17)."
                )
        self.estado = 'HABILITADA'
        self.fecha_ocupacion = None
        if guardar and self.pk:
            self.save(update_fields=['estado', 'fecha_ocupacion'])
        return self

    def get_resumen_ocupacion(self):
        """Retorna un diccionario completo con las métricas de estado y ocupación de la mesa (RF17)"""
        from ventas.utils import formatear_fecha_hora_chile
        va = self.get_venta_activa()
        inicio = self.get_inicio_ocupacion()
        return {
            'mesa_id': self.id,
            'identificador': self.identificador,
            'punto_venta_id': self.punto_venta_id,
            'punto_venta_nombre': self.punto_venta.nombre if self.punto_venta else None,
            'capacidad': self.capacidad,
            'estado': self.estado,
            'esta_ocupada': self.esta_ocupada(),
            'esta_disponible': self.esta_disponible(),
            'inicio_ocupacion': inicio,
            'inicio_ocupacion_chile': formatear_fecha_hora_chile(inicio),
            'duracion_ocupacion_minutos': self.get_duracion_ocupacion_minutos(),
            'duracion_ocupacion_segundos': self.get_duracion_ocupacion_segundos(),
            'tiene_cuenta_abierta': va is not None,
            'venta_abierta_id': va.id if va else None,
            'total_cuenta_abierta': int(va.total) if va else 0,
            'rondas_comanda': va.pedidos.count() if va else 0,
        }

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
        ('VENTA_RAPIDA', 'Venta Rápida / Retiro en Mostrador'),
        ('MOSTRADOR', 'Venta Rápida / Mostrador'),
        ('MESA', 'Consumo en Mesa (Salón)'),
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

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError

        # Normalizar alias de venta rápida
        if self.modalidad in ['MOSTRADOR', 'LLEVAR', 'RETIRO']:
            self.modalidad = 'VENTA_RAPIDA'

        if self.modalidad == 'MESA':
            if not self.mesa:
                raise ValidationError("Una venta con modalidad 'MESA' requiere obligatoriamente una mesa asignada (RF11.1).")
            if self.punto_venta and self.mesa.punto_venta_id != self.punto_venta_id:
                raise ValidationError("La mesa asignada debe pertenecer al mismo punto de venta de la operación.")
            # Si la cuenta está abierta, validar que no haya otra cuenta abierta distinta en la misma mesa
            if self.estado == 'ABIERTA' and self.mesa_id:
                otra_abierta = Venta.objects.filter(
                    mesa_id=self.mesa_id,
                    estado='ABIERTA'
                ).exclude(pk=self.pk).first()
                if otra_abierta:
                    raise ValidationError(f"La mesa {self.mesa.identificador} ya tiene una cuenta abierta en curso (Venta #{otra_abierta.id}).")
        elif self.modalidad == 'VENTA_RAPIDA':
            # Venta rápida / retiro no bloquea ni ocupa mesa física (RF11.3)
            if self.mesa is not None:
                self.mesa = None

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def es_consumo_en_mesa(self):
        """Indica si la comanda corresponde a servicio en salón con mesa asignada (RF11.1)"""
        return self.modalidad == 'MESA' and self.mesa is not None

    def es_venta_rapida(self):
        """Indica si la comanda corresponde a retiro rápido / mostrador (RF11.3)"""
        return self.modalidad in ['VENTA_RAPIDA', 'MOSTRADOR']

    def get_ubicacion_despacho(self):
        """Retorna la ubicación operativa formal para comandas y despacho KDS/BDS (RF11)"""
        if self.es_consumo_en_mesa():
            return f"Mesa {self.mesa.identificador} (Salón)"
        return "Retiro Rápido / Mostrador"

    def __str__(self):
        return f"Venta #{self.id} (${self.total:,.0f}) - {self.get_modalidad_display()}"

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ['-fecha_hora']


# ==============================================================================
# 10.1 REASIGNACIÓN DE MESAS (RF05 - Reasignación y Trazabilidad de Cuentas)
# ==============================================================================
class ReasignacionMesa(models.Model):
    """Auditoría histórica de traslados de comensales y cuentas abiertas entre mesas (RF05)"""
    venta = models.ForeignKey('Venta', on_delete=models.CASCADE, related_name='reasignaciones_mesa')
    mesa_origen = models.ForeignKey(Mesa, on_delete=models.PROTECT, related_name='traslados_origen')
    mesa_destino = models.ForeignKey(Mesa, on_delete=models.PROTECT, related_name='traslados_destino')
    mesero = models.ForeignKey(User, on_delete=models.PROTECT, related_name='reasignaciones_realizadas')
    motivo = models.CharField(max_length=200, blank=True, null=True, default="Solicitud de cambio de mesa por comensal")
    fecha_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Traslado Venta #{self.venta.id}: {self.mesa_origen.identificador} -> {self.mesa_destino.identificador} ({self.mesero.username})"

    class Meta:
        verbose_name = "Reasignación de Mesa"
        verbose_name_plural = "Reasignaciones de Mesas"
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
    # Campos RF07 - Trazabilidad de Precios Especiales y Convenios
    precio_original = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Precio base oficial de Producto en BD")
    es_precio_especial = models.BooleanField(default=False, help_text="Indica si se aplicó precio especial o convenio (RF07)")
    motivo_precio_especial = models.CharField(max_length=200, blank=True, null=True, help_text="Motivo o convenio comercial (RF07)")
    autorizado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='precios_especiales_autorizados')

    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre} en Venta #{self.venta.id}"

    class Meta:
        verbose_name = "Detalle de Venta"
        verbose_name_plural = "Detalles de Venta"


# ==============================================================================
# 11.1 REGISTRO DE PRECIOS ESPECIALES Y CONVENIOS (RF07 - Trazabilidad de Precios)
# ==============================================================================
class RegistroPrecioEspecial(models.Model):
    """Auditoría de precios especiales, convenios y descuentos autorizados durante la venta (RF07)"""
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='registros_precios_especiales')
    detalle_venta = models.ForeignKey(DetalleVenta, on_delete=models.CASCADE, related_name='registros_precio_especial', null=True, blank=True)
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='historial_precios_especiales')
    precio_original = models.DecimalField(max_digits=10, decimal_places=2, help_text="Precio base del producto al momento de la venta")
    precio_aplicado = models.DecimalField(max_digits=10, decimal_places=2, help_text="Precio especial efectivamente cobrado")
    descuento_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Diferencia unitaria entre precio base y precio aplicado")
    cantidad = models.PositiveIntegerField(default=1)
    usuario = models.ForeignKey(User, on_delete=models.PROTECT, related_name='precios_especiales_aplicados', help_text="Usuario que aplicó o autorizó la modificación")
    motivo = models.CharField(max_length=200, help_text="Motivo comercial, convenio o condición autorizada")
    convenio_origen = models.ForeignKey(PrecioEspecial, on_delete=models.SET_NULL, null=True, blank=True, related_name='aplicaciones', help_text="Convenio institucional si proviene de PrecioEspecial")
    fecha_hora = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"RF07 Venta #{self.venta.id} - {self.producto.nombre}: ${self.precio_original:,.0f} -> ${self.precio_aplicado:,.0f} ({self.motivo})"

    class Meta:
        verbose_name = "Registro de Precio Especial"
        verbose_name_plural = "Registros de Precios Especiales"
        ordering = ['-fecha_hora']

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
    fecha_inicio_preparacion = models.DateTimeField(null=True, blank=True, help_text="Timestamp de inicio de preparación en cocina/barra (RF13/RF16)")
    fecha_listo = models.DateTimeField(null=True, blank=True, help_text="Timestamp de marcado como listo para servir (RF13/RF16)")

    @property
    def fecha_entregado(self):
        """Retorna el timestamp de la primera entrega registrada o el valor asignado manualmente (RF16)"""
        if hasattr(self, '_fecha_entregado_override'):
            return self._fecha_entregado_override
        if not self.pk:
            return None
        try:
            entrega = self.entregas.order_by('id').first()
            return entrega.fecha_hora_entrega if entrega else None
        except Exception:
            return None

    @fecha_entregado.setter
    def fecha_entregado(self, value):
        """Permite asignar o simular timestamp de entrega en memoria/tests (RF16)"""
        self._fecha_entregado_override = value

    def _calcular_delta_segundos(self, dt_fin, dt_inicio):
        """Calcula la diferencia en segundos entre dos datetimes de forma robusta con zonas horarias (RF16)"""
        if not dt_fin or not dt_inicio:
            return None
        if timezone.is_naive(dt_fin) and timezone.is_aware(dt_inicio):
            dt_fin = timezone.make_aware(dt_fin, timezone.get_current_timezone())
        elif timezone.is_aware(dt_fin) and timezone.is_naive(dt_inicio):
            dt_inicio = timezone.make_aware(dt_inicio, timezone.get_current_timezone())
        return (dt_fin - dt_inicio).total_seconds()

    def get_tiempo_cola_minutos(self, en_curso=False):
        """Retorna el tiempo en cola en minutos desde creación hasta inicio de preparación (RF16)"""
        if self.creado_en and self.fecha_inicio_preparacion:
            segundos = self._calcular_delta_segundos(self.fecha_inicio_preparacion, self.creado_en)
            return max(0.0, round(segundos / 60.0, 1)) if segundos is not None else None
        if en_curso and self.creado_en and self.estado == 'PENDIENTE':
            segundos = self._calcular_delta_segundos(timezone.now(), self.creado_en)
            return max(0.0, round(segundos / 60.0, 1)) if segundos is not None else None
        return None

    def get_tiempo_cola_segundos(self, en_curso=False):
        """Retorna el tiempo en cola en segundos (RF16)"""
        minutos = self.get_tiempo_cola_minutos(en_curso=en_curso)
        return int(minutos * 60) if minutos is not None else None

    def get_tiempo_preparacion_minutos(self, en_curso=False):
        """Retorna el tiempo de preparación en minutos desde inicio hasta marcado como listo (RF16)"""
        if self.fecha_inicio_preparacion and self.fecha_listo:
            segundos = self._calcular_delta_segundos(self.fecha_listo, self.fecha_inicio_preparacion)
            return max(0.0, round(segundos / 60.0, 1)) if segundos is not None else None
        if en_curso and self.fecha_inicio_preparacion and self.estado == 'EN_PREPARACION':
            segundos = self._calcular_delta_segundos(timezone.now(), self.fecha_inicio_preparacion)
            return max(0.0, round(segundos / 60.0, 1)) if segundos is not None else None
        return None

    def get_tiempo_preparacion_segundos(self, en_curso=False):
        """Retorna el tiempo de preparación en segundos (RF16)"""
        minutos = self.get_tiempo_preparacion_minutos(en_curso=en_curso)
        return int(minutos * 60) if minutos is not None else None

    def get_tiempo_despacho_minutos(self, en_curso=False):
        """Retorna el tiempo de despacho en minutos desde que estuvo listo hasta su entrega (RF16)"""
        fe = self.fecha_entregado
        if self.fecha_listo and fe:
            segundos = self._calcular_delta_segundos(fe, self.fecha_listo)
            return max(0.0, round(segundos / 60.0, 1)) if segundos is not None else None
        if en_curso and self.fecha_listo and self.estado == 'LISTO':
            segundos = self._calcular_delta_segundos(timezone.now(), self.fecha_listo)
            return max(0.0, round(segundos / 60.0, 1)) if segundos is not None else None
        return None

    def get_tiempo_despacho_segundos(self, en_curso=False):
        """Retorna el tiempo de despacho en segundos (RF16)"""
        minutos = self.get_tiempo_despacho_minutos(en_curso=en_curso)
        return int(minutos * 60) if minutos is not None else None

    def get_tiempo_espera_total_minutos(self, en_curso=False):
        """
        Retorna el tiempo transcurrido desde la creación del pedido hasta su entrega (RF16).
        Si el pedido aún no está entregado y no se solicita cálculo en curso, retorna None para no inventar tiempos.
        """
        fe = self.fecha_entregado
        if not fe and not en_curso:
            return None
        fin = fe if fe else timezone.now()
        if self.creado_en and fin:
            segundos = self._calcular_delta_segundos(fin, self.creado_en)
            return max(0.0, round(segundos / 60.0, 1)) if segundos is not None else None
        return None

    def get_tiempo_espera_total_segundos(self, en_curso=False):
        """Retorna el tiempo de espera total en segundos (RF16)"""
        minutos = self.get_tiempo_espera_total_minutos(en_curso=en_curso)
        return int(minutos * 60) if minutos is not None else None

    def validar_orden_temporal(self):
        """
        Valida que la secuencia de timestamps sea cronológicamente coherente:
        creado_en <= fecha_inicio_preparacion <= fecha_listo <= fecha_entregado.
        Retorna (es_valido, lista_inconsistencias).
        """
        inconsistencias = []
        fe = self.fecha_entregado

        if self.creado_en and self.fecha_inicio_preparacion:
            seg = self._calcular_delta_segundos(self.fecha_inicio_preparacion, self.creado_en)
            if seg is not None and seg < 0:
                inconsistencias.append(
                    f"fecha_inicio_preparacion ({self.fecha_inicio_preparacion}) es anterior a creado_en ({self.creado_en})"
                )

        if self.fecha_inicio_preparacion and self.fecha_listo:
            seg = self._calcular_delta_segundos(self.fecha_listo, self.fecha_inicio_preparacion)
            if seg is not None and seg < 0:
                inconsistencias.append(
                    f"fecha_listo ({self.fecha_listo}) es anterior a fecha_inicio_preparacion ({self.fecha_inicio_preparacion})"
                )

        if self.fecha_listo and fe:
            seg = self._calcular_delta_segundos(fe, self.fecha_listo)
            if seg is not None and seg < 0:
                inconsistencias.append(
                    f"fecha_entregado ({fe}) es anterior a fecha_listo ({self.fecha_listo})"
                )

        if self.creado_en and fe:
            seg = self._calcular_delta_segundos(fe, self.creado_en)
            if seg is not None and seg < 0:
                inconsistencias.append(
                    f"fecha_entregado ({fe}) es anterior a creado_en ({self.creado_en})"
                )

        es_valido = len(inconsistencias) == 0
        return (es_valido, inconsistencias)

    def get_metricas_tiempos(self, en_curso=False):
        """Retorna un diccionario estructurado con todas las métricas de tiempos de atención (RF16)"""
        valido, inconsistencias = self.validar_orden_temporal()
        return {
            'pedido_id': self.id,
            'estado': self.estado,
            'creado_en': self.creado_en,
            'fecha_inicio_preparacion': self.fecha_inicio_preparacion,
            'fecha_listo': self.fecha_listo,
            'fecha_entregado': self.fecha_entregado,
            'tiempo_cola_minutos': self.get_tiempo_cola_minutos(en_curso=en_curso),
            'tiempo_cola_segundos': self.get_tiempo_cola_segundos(en_curso=en_curso),
            'tiempo_preparacion_minutos': self.get_tiempo_preparacion_minutos(en_curso=en_curso),
            'tiempo_preparacion_segundos': self.get_tiempo_preparacion_segundos(en_curso=en_curso),
            'tiempo_despacho_minutos': self.get_tiempo_despacho_minutos(en_curso=en_curso),
            'tiempo_despacho_segundos': self.get_tiempo_despacho_segundos(en_curso=en_curso),
            'tiempo_espera_total_minutos': self.get_tiempo_espera_total_minutos(en_curso=en_curso),
            'tiempo_espera_total_segundos': self.get_tiempo_espera_total_segundos(en_curso=en_curso),
            'orden_temporal_valido': valido,
            'inconsistencias_temporales': inconsistencias,
            'esta_entregado': self.fecha_entregado is not None,
            'en_curso': en_curso,
        }

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

    def clean(self):
        super().clean()
        if self.observaciones:
            from ventas.utils import sanitizar_observacion
            self.observaciones = sanitizar_observacion(self.observaciones, max_length=200)
        else:
            self.observaciones = None

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cantidad}x {self.producto.nombre} (Pedido #{self.pedido.id})"

    class Meta:
        verbose_name = "Detalle de Pedido"
        verbose_name_plural = "Detalles de Pedido"


# ==============================================================================
# 14. TICKETS DE PRODUCCIÓN E IMPRESIÓN (RF10 - Tickets Cocina / Barra / Cliente)
# ==============================================================================
class Ticket(models.Model):
    """Ticket físico/virtual con destino operativo (Cocina, Barra o Comprobante) (RF08)"""
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
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, null=True, blank=True, related_name='tickets')
    venta = models.ForeignKey('Venta', on_delete=models.CASCADE, null=True, blank=True, related_name='tickets_asociados', help_text="Venta asociada al ticket (RF08)")
    codigo = models.CharField(max_length=30, unique=True, help_text="Ej: COM-0085, TIK-C-0102")
    tipo_destino = models.CharField(max_length=20, choices=DESTINOS, default='COCINA')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='EMITIDO')
    fecha_hora = models.DateTimeField(auto_now_add=True)
    contenido_impresion = models.TextField(blank=True, null=True, help_text="Texto listo para impresora térmica futura")
    # Campos RF08.6: Reimpresión Trazable
    es_reimpresion = models.BooleanField(default=False, help_text="Indica si este ticket ha sido reimpreso (RF08.6)")
    numero_reimpresiones = models.PositiveIntegerField(default=0, help_text="Contador de veces reimpreso")
    ultima_reimpresion_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_reimpresos')
    fecha_hora_reimpresion = models.DateTimeField(null=True, blank=True)
    # Campos RF09: Gestión de Impresión y Despacho
    punto_venta = models.ForeignKey(PuntoVenta, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets', help_text="Local/Punto de Venta emisor (RF09)")
    punto_impresion = models.ForeignKey('PuntoImpresion', on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets_despachados', help_text="Punto de impresión enrutado (RF09)")
    estado_impresion = models.CharField(
        max_length=20,
        choices=[('PENDIENTE', 'Pendiente de Envío'), ('IMPRESO', 'Impreso / Enviado'), ('FALLO', 'Fallo de Impresión')],
        default='IMPRESO',
        help_text="Estado del despacho físico o digital (RF09)"
    )
    error_impresion = models.TextField(blank=True, null=True, help_text="Detalle del error si falló la impresión (RF09)")
    intentos_impresion = models.PositiveIntegerField(default=1, help_text="Contador de intentos de despacho (RF09)")

    def get_punto_venta(self):
        if self.punto_venta:
            return self.punto_venta
        if self.venta and self.venta.punto_venta:
            return self.venta.punto_venta
        if self.pedido and self.pedido.venta:
            if self.pedido.venta.punto_venta:
                return self.pedido.venta.punto_venta
            if self.pedido.venta.mesa and self.pedido.venta.mesa.punto_venta:
                return self.pedido.venta.mesa.punto_venta
        return None

    def __str__(self):
        return f"Ticket #{self.codigo} [{self.get_tipo_destino_display()}] - {self.get_estado_display()} (Impresión: {self.get_estado_impresion_display()})"

    class Meta:
        verbose_name = "Ticket de Producción"
        verbose_name_plural = "Tickets de Producción"
        ordering = ['-fecha_hora']


# ==============================================================================


# ==============================================================================
# 14.1 PUNTOS DE IMPRESIÓN Y AUDITORÍA DE DESPACHO (RF09)
# ==============================================================================
class PuntoImpresion(models.Model):
    """Punto de impresión físico o digital para restaurante/bar/caja (RF09)"""
    TIPO_DESTINOS = [
        ('COCINA', 'Cocina Caliente'),
        ('BARRA', 'Barra / Cafetería'),
        ('COMPROBANTE', 'Caja / Boleta de Venta'),
    ]
    TIPO_CONEXION = [
        ('DIGITAL', 'Digital / Previsualización en Pantalla (Navegador)'),
        ('RED', 'Impresora Térmica de Red (Ethernet / WiFi RAW ESC/POS)'),
        ('USB', 'Impresora Térmica USB / Spooler'),
    ]
    ESTADOS = [
        ('ONLINE', 'En Línea / Operativa'),
        ('OFFLINE', 'Fuera de Línea / Desconectada'),
        ('SIN_PAPEL', 'Sin Papel'),
        ('ERROR', 'Error de Comunicación'),
    ]

    nombre = models.CharField(max_length=100, help_text="Ej: Impresora Térmica Cocina Central")
    punto_venta = models.ForeignKey(PuntoVenta, on_delete=models.CASCADE, related_name='puntos_impresion')
    tipo_destino = models.CharField(max_length=20, choices=TIPO_DESTINOS)
    tipo_conexion = models.CharField(max_length=20, choices=TIPO_CONEXION, default='DIGITAL')
    direccion_ip = models.CharField(max_length=100, blank=True, null=True, help_text="Ej: 192.168.1.201")
    puerto = models.PositiveIntegerField(default=9100, help_text="Puerto RAW ESC/POS (típicamente 9100)")
    ancho_papel_mm = models.PositiveIntegerField(default=80, choices=[(80, '80 mm'), (58, '58 mm')])
    estado_operativo = models.CharField(max_length=20, choices=ESTADOS, default='ONLINE')
    activo = models.BooleanField(default=True)
    simular_fallo = models.BooleanField(default=False, help_text="Para pruebas y contingencia: simula fallo físico de impresión sin bloquear venta")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Punto de Impresión"
        verbose_name_plural = "Puntos de Impresión"
        unique_together = ('punto_venta', 'tipo_destino')

    def __str__(self):
        return f"{self.nombre} [{self.get_tipo_destino_display()}] - {self.punto_venta.nombre} ({self.get_estado_operativo_display()})"


class RegistroImpresion(models.Model):
    """Auditoría de despachos y reintentos de impresión (RF09)"""
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='registros_impresion')
    punto_impresion = models.ForeignKey(PuntoImpresion, on_delete=models.SET_NULL, null=True, blank=True, related_name='registros_despacho')
    exitoso = models.BooleanField(default=True)
    modo = models.CharField(max_length=20, default='DIGITAL')
    mensaje_error = models.TextField(blank=True, null=True)
    es_reintento = models.BooleanField(default=False)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='despachos_impresion')
    fecha_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de Impresión"
        verbose_name_plural = "Registros de Impresión"
        ordering = ['-fecha_hora']

    def __str__(self):
        estado_str = "EXITOSO" if self.exitoso else "FALLIDO"
        return f"Registro #{self.id} Ticket #{self.ticket.codigo} [{estado_str}] - {self.fecha_hora.strftime('%d/%m/%Y %H:%M')}"

# 15. ENTREGA DE PEDIDOS (RF11 - Medición de tiempos de entrega)
# ==============================================================================
class Entrega(models.Model):
    """Marca de tiempo de entrega final al comensal para auditoría de tiempos de servicio"""
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='entregas')
    ticket = models.ForeignKey(Ticket, on_delete=models.SET_NULL, null=True, blank=True, related_name='entregas')
    usuario_entrega = models.ForeignKey(User, on_delete=models.PROTECT, related_name='entregas_realizadas', null=True, blank=True)
    fecha_hora_entrega = models.DateTimeField(auto_now_add=True)
    observaciones = models.CharField(max_length=200, blank=True, null=True)

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.pedido:
            if self.pedido.estado == 'CANCELADO':
                raise ValidationError("No se puede registrar entrega para un pedido cancelado.")
            if self.pedido.estado not in ['LISTO', 'ENTREGADO']:
                raise ValidationError(f"El pedido #{self.pedido.id} debe estar en estado 'LISTO' para ser entregado (estado actual: {self.pedido.get_estado_display()}) (RF13.1).")
            if not self.pk and Entrega.objects.filter(pedido=self.pedido).exists():
                raise ValidationError(f"El pedido #{self.pedido.id} ya registra una entrega previa (RF13.4).")
        if self.observaciones:
            from ventas.utils import sanitizar_observacion
            self.observaciones = sanitizar_observacion(self.observaciones, max_length=200)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def get_ubicacion(self):
        """Retorna la ubicación operativa formal de la comanda (RF11 / RF13)"""
        if self.pedido and self.pedido.venta:
            return self.pedido.venta.get_ubicacion_despacho()
        return "Retiro Rápido / Mostrador"

    def get_punto_venta(self):
        """Retorna el Punto de Venta donde se despachó el pedido (RF13.2)"""
        if self.pedido and self.pedido.venta:
            if self.pedido.venta.punto_venta:
                return self.pedido.venta.punto_venta
            if self.pedido.venta.mesa and self.pedido.venta.mesa.punto_venta:
                return self.pedido.venta.mesa.punto_venta
        if self.ticket and self.ticket.punto_venta:
            return self.ticket.punto_venta
        return None

    def get_tiempo_desde_creacion_minutos(self):
        """Retorna los minutos transcurridos desde que se generó la comanda hasta su entrega final (RF13 / RF16)"""
        if self.pedido and self.pedido.creado_en and self.fecha_hora_entrega:
            delta = self.fecha_hora_entrega - self.pedido.creado_en
            return max(0.0, round(delta.total_seconds() / 60.0, 1))
        return 0.0

    def get_tiempo_desde_creacion_segundos(self):
        """Retorna los segundos transcurridos desde la creación del pedido hasta su entrega (RF13 / RF16)"""
        if self.pedido and self.pedido.creado_en and self.fecha_hora_entrega:
            delta = self.fecha_hora_entrega - self.pedido.creado_en
            return max(0, int(delta.total_seconds()))
        return 0

    def get_tiempo_desde_listo_minutos(self):
        """Retorna los minutos transcurridos desde que el pedido estuvo listo hasta su entrega (RF16)"""
        if self.pedido and self.pedido.fecha_listo and self.fecha_hora_entrega:
            delta = self.fecha_hora_entrega - self.pedido.fecha_listo
            return max(0.0, round(delta.total_seconds() / 60.0, 1))
        return None

    def get_tiempo_desde_listo_segundos(self):
        """Retorna los segundos transcurridos desde que el pedido estuvo listo hasta su entrega (RF16)"""
        if self.pedido and self.pedido.fecha_listo and self.fecha_hora_entrega:
            delta = self.fecha_hora_entrega - self.pedido.fecha_listo
            return max(0, int(delta.total_seconds()))
        return None

    def __str__(self):
        return f"Entrega Pedido #{self.pedido.id} ({self.fecha_hora_entrega.strftime('%H:%M:%S')}) - {self.get_ubicacion()}"

    class Meta:
        verbose_name = "Entrega de Pedido"
        verbose_name_plural = "Entregas de Pedidos"
        ordering = ['-fecha_hora_entrega']


# ==============================================================================
# 16. CONSUMO INTERNO DE TRABAJADORES (RF12 - Registro de Fiado / Consumo Personal)
# ==============================================================================
class ConsumoInterno(models.Model):
    """Registro de colaciones o consumos de colaboradores para descuento de personal / fiado (RF10)"""
    ESTADOS = [
        ('REGISTRADO', 'Registrado / Pendiente Descuento'),
        ('DESCONTADO', 'Descontado por Planilla'),
        ('ANULADO', 'Anulado'),
    ]
    TIPOS_CONSUMO = [
        ('FIADO', 'Fiado / Descuento Planilla'),
        ('COLACION', 'Colación Autorizada'),
        ('CORTESIA', 'Cortesía Institucional'),
    ]
    empleado = models.ForeignKey(User, on_delete=models.PROTECT, related_name='consumos_internos', help_text="Trabajador beneficiario")
    punto_venta = models.ForeignKey(PuntoVenta, on_delete=models.PROTECT, related_name='consumos_internos', help_text="Local donde se consumió")
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='REGISTRADO')
    tipo_consumo = models.CharField(max_length=20, choices=TIPOS_CONSUMO, default='FIADO', help_text="Modalidad de consumo (RF10.2)")
    registrado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='consumos_registrados', help_text="Cajero/Admin que registró (RF10.2)")
    caja = models.ForeignKey('Caja', on_delete=models.SET_NULL, null=True, blank=True, related_name='consumos_internos', help_text="Caja operativa del turno")
    fecha_hora = models.DateTimeField(auto_now_add=True)
    observaciones = models.TextField(blank=True, null=True)
    descontado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='consumos_liquidados', help_text="Supervisor que liquidó")
    fecha_hora_descuento = models.DateTimeField(null=True, blank=True)

    def recalcular_total(self):
        total_calc = sum(d.subtotal for d in self.detalles.all())
        self.total = total_calc
        self.save(update_fields=['total'])
        return self.total

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
        hoy = timezone.localdate()
        return self.activo and (self.fecha_checkin <= hoy <= self.fecha_checkout)

    def consumos_hoy_count(self):
        """Calcula cuantas veces ha utilizado el beneficio durante la jornada de hoy"""
        hoy = timezone.localdate()
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

