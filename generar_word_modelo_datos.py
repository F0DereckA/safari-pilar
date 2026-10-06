import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

# ==============================================================================
# 1. GENERACIÓN DEL DIAGRAMA ERD EN ALTA RESOLUCIÓN (MATPLOTLIB)
# ==============================================================================
def generar_imagen_erd(output_path):
    fig, ax = plt.subplots(figsize=(20, 14), dpi=300)
    ax.set_xlim(0, 20)
    ax.set_ylim(0, 14)
    ax.axis('off')

    # Paleta de colores Safari
    colors = {
        'admin': '#B91C1C',    # Rojo Safari (Usuarios / Roles / Alertas)
        'locales': '#1E3A8A',  # Azul Marino (Puntos de Venta / Mesas)
        'jornada': '#D97706',  # Ámbar (Jornada / Cajas)
        'catalogo': '#047857', # Verde Esmeralda (Categorías / Productos / Menús)
        'ventas': '#4338CA',   # Índigo (Ventas / Comandas / Tickets)
        'personal': '#475569', # Gris Azulado (Consumo Interno)
        'bg_header': '#F8FAFC',
        'border': '#CBD5E1'
    }

    # Definición de tablas y sus posiciones (x, y, w, h, modulo, titulo, campos)
    tables = [
        # Columna 1: Seguridad y Personal (x: 0.8)
        (0.8, 8.8, 3.2, 3.6, 'admin', 'auth_user', [
            'id : INT [PK]',
            'username : VARCHAR(150) [UQ]',
            'first_name : VARCHAR(150)',
            'last_name : VARCHAR(150)',
            'email : VARCHAR(254)',
            'password : VARCHAR(128)',
            'is_active : BOOLEAN'
        ]),
        (0.8, 4.6, 3.2, 3.4, 'admin', 'perfil_empleado', [
            'id : INT [PK]',
            'usuario_id : INT [FK, UQ]',
            'rol : VARCHAR(20)',
            'rut : VARCHAR(12)',
            'punto_venta_id : INT [FK]',
            'activo : BOOLEAN'
        ]),
        (0.8, 0.8, 3.2, 3.0, 'admin', 'alerta_traslado', [
            'id : INT [PK]',
            'empleado_id : INT [FK]',
            'origen_id : INT [FK]',
            'destino_id : INT [FK]',
            'autorizado_por : INT [FK]',
            'fecha_hora : TIMESTAMP'
        ]),

        # Columna 2: Locales, Jornada y Cajas (x: 4.7)
        (4.7, 8.8, 3.2, 3.6, 'locales', 'punto_venta', [
            'id : INT [PK]',
            'nombre : VARCHAR(100) [UQ]',
            'tipo : VARCHAR(50)',
            'icono : VARCHAR(50)',
            'color : VARCHAR(20)',
            'activo : BOOLEAN',
            'creado_en : TIMESTAMP'
        ]),
        (4.7, 4.8, 3.2, 3.2, 'jornada', 'jornada', [
            'id : INT [PK]',
            'fecha : DATE',
            'estado : VARCHAR(15)',
            'usuario_apertura : INT [FK]',
            'usuario_cierre : INT [FK]',
            'apertura : TIMESTAMP'
        ]),
        (4.7, 0.8, 3.2, 3.3, 'jornada', 'caja', [
            'id : INT [PK]',
            'nombre : VARCHAR(50)',
            'punto_venta_id : INT [FK]',
            'jornada_id : INT [FK]',
            'cajero_id : INT [FK]',
            'monto_apertura : DECIMAL',
            'UQ(jornada, cajero)'
        ]),

        # Columna 3: Mesas y Catálogo (x: 8.6)
        (8.6, 9.1, 3.2, 3.3, 'locales', 'mesa', [
            'id : INT [PK]',
            'identificador : VARCHAR(20)',
            'punto_venta_id : INT [FK]',
            'capacidad : INT',
            'estado : VARCHAR(20)',
            'UQ(identificador, local)'
        ]),
        (8.6, 5.0, 3.2, 3.3, 'catalogo', 'categoria', [
            'id : INT [PK]',
            'nombre : VARCHAR(100) [UQ]',
            'descripcion : TEXT',
            'activo : BOOLEAN'
        ]),
        (8.6, 0.8, 3.2, 3.6, 'catalogo', 'producto', [
            'id : INT [PK]',
            'nombre : VARCHAR(150)',
            'categoria_id : INT [FK]',
            'precio_base : DECIMAL(10,2)',
            'descripcion : TEXT',
            'activo : BOOLEAN'
        ]),

        # Columna 4: Ventas y Comandas (x: 12.5)
        (12.5, 7.8, 3.3, 4.6, 'ventas', 'venta', [
            'id : INT [PK]',
            'caja_id : INT [FK]',
            'cajero_id : INT [FK]',
            'punto_venta_id : INT [FK]',
            'mesa_id : INT [FK, NULL]',
            'modalidad : VARCHAR(20)',
            'metodo_pago : VARCHAR(20)',
            'total : DECIMAL(12,2)',
            'estado : VARCHAR(20)'
        ]),
        (12.5, 4.0, 3.3, 3.1, 'ventas', 'detalle_venta', [
            'id : INT [PK]',
            'venta_id : INT [FK]',
            'producto_id : INT [FK]',
            'cantidad : INT',
            'precio_aplicado : DECIMAL',
            'subtotal : DECIMAL(10,2)'
        ]),
        (12.5, 0.8, 3.3, 2.6, 'catalogo', 'menu', [
            'id : INT [PK]',
            'nombre : VARCHAR(100)',
            'punto_venta_id : INT [FK]',
            'activo : BOOLEAN'
        ]),

        # Columna 5: Producción y Tickets (x: 16.4)
        (16.4, 8.8, 2.8, 3.6, 'ventas', 'pedido', [
            'id : INT [PK]',
            'venta_id : INT [FK]',
            'estado : VARCHAR(20)',
            'observaciones : TEXT',
            'creado_en : TIMESTAMP'
        ]),
        (16.4, 5.2, 2.8, 2.9, 'ventas', 'detalle_pedido', [
            'id : INT [PK]',
            'pedido_id : INT [FK]',
            'producto_id : INT [FK]',
            'cantidad : INT',
            'nota : VARCHAR(200)'
        ]),
        (16.4, 1.8, 2.8, 2.7, 'ventas', 'ticket', [
            'id : INT [PK]',
            'pedido_id : INT [FK]',
            'codigo : VARCHAR(30) [UQ]',
            'tipo_destino : VARCHAR(20)',
            'estado : VARCHAR(20)'
        ]),
    ]

    # Dibujar cajas de tablas
    for x, y, w, h, mod, name, fields in tables:
        # Borde exterior con sombra sutil
        rect_shadow = patches.FancyBboxPatch((x+0.04, y-0.04), w, h, boxstyle="round,pad=0.03", fc='#E2E8F0', ec='none', zorder=1)
        ax.add_patch(rect_shadow)
        rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.03", fc='#FFFFFF', ec='#94A3B8', lw=1.2, zorder=2)
        ax.add_patch(rect)

        # Encabezado con color del módulo
        header_h = 0.65
        header = patches.FancyBboxPatch((x, y + h - header_h), w, header_h, boxstyle="round,pad=0.01", fc=colors[mod], ec='none', zorder=3)
        ax.add_patch(header)
        ax.text(x + w/2, y + h - header_h/2, name.upper(), color='white', weight='bold', fontsize=9.5, ha='center', va='center', zorder=4)

        # Líneas de campos
        line_y = y + h - header_h - 0.28
        for f in fields:
            is_pk = '[PK]' in f
            is_fk = '[FK]' in f
            color_txt = '#0F172A' if (is_pk or is_fk) else '#475569'
            weight = 'bold' if is_pk else 'normal'
            ax.text(x + 0.15, line_y, f, fontsize=7.2, color=color_txt, weight=weight, zorder=4)
            line_y -= 0.38

    # Conectores / Flechas de relaciones principales (enrutadas limpiamente por bordes)
    arrows = [
        # auth_user -> perfil_empleado (vertical directo)
        (2.4, 8.8, 2.4, 8.0, '#B91C1C'),
        # perfil_empleado -> alerta_traslado (vertical directo)
        (2.4, 4.6, 2.4, 3.8, '#B91C1C'),
        # punto_venta -> perfil_empleado (horizontal lateral)
        (4.7, 9.2, 4.0, 6.5, '#1E3A8A'),
        # auth_user -> jornada (conector limpio)
        (4.0, 10.5, 4.7, 7.0, '#D97706'),
        # jornada -> caja (vertical directo)
        (6.3, 4.8, 6.3, 4.1, '#D97706'),
        # punto_venta -> caja (vertical por el lateral)
        (5.2, 8.8, 5.2, 4.1, '#1E3A8A'),
        # punto_venta -> mesa (horizontal directo)
        (7.9, 10.5, 8.6, 10.5, '#1E3A8A'),
        # categoria -> producto (vertical directo)
        (10.2, 5.0, 10.2, 4.4, '#047857'),
        # mesa -> venta (horizontal limpio)
        (11.8, 10.5, 12.5, 10.5, '#1E3A8A'),
        # venta -> detalle_venta (vertical directo)
        (14.1, 7.8, 14.1, 7.1, '#4338CA'),
        # producto -> detalle_venta (diagonal limpia desde borde superior derecho de producto)
        (11.8, 4.0, 12.5, 5.2, '#047857'),
        # caja -> venta (conector lateral inferior limpio)
        (7.9, 2.0, 12.5, 8.2, '#4338CA'),
        # venta -> pedido (horizontal directo)
        (15.8, 10.5, 16.4, 10.5, '#4338CA'),
        # pedido -> detalle_pedido (vertical directo)
        (17.8, 8.8, 17.8, 8.1, '#4338CA'),
        # pedido -> ticket (vertical por el lateral)
        (18.5, 8.8, 18.5, 4.5, '#4338CA'),
    ]

    for x1, y1, x2, y2, c in arrows:
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color=c, lw=1.4, shrinkA=3, shrinkB=3), zorder=5)

    # Título del Diagrama (bien espaciado arriba)
    ax.text(10.0, 13.5, "MODELO RELACIONAL DE BASE DE DATOS - PARQUE SAFARI",
            fontsize=16, weight='bold', color='#1E293B', ha='center', va='center')
    ax.text(10.0, 13.05, "Diagrama Entidad-Relación Lógico Normalizado (Tercera Forma Normal - 3NF)",
            fontsize=11, color='#64748B', ha='center', va='center')

    # Leyenda de Módulos al pie
    legend_items = [
        ('Seguridad & Personal', colors['admin']),
        ('Puntos de Venta & Mesas', colors['locales']),
        ('Jornada & Cajas', colors['jornada']),
        ('Catálogo & Menús', colors['catalogo']),
        ('Ventas, Comandas & Tickets', colors['ventas']),
    ]
    leg_x = 2.0
    for lbl, col in legend_items:
        ax.add_patch(patches.Rectangle((leg_x, 0.15), 0.35, 0.25, fc=col, ec='none'))
        ax.text(leg_x + 0.45, 0.27, lbl, fontsize=8.5, color='#334155', va='center')
        leg_x += 3.3

    plt.tight_layout()
    fig.savefig(output_path, bbox_inches='tight', dpi=300)
    plt.close(fig)
    print(f"[+] Diagrama ERD mejorado en: {output_path}")


# ==============================================================================
# 2. GENERACIÓN DEL DOCUMENTO WORD (.DOCX) PROFESIONAL
# ==============================================================================
def set_cell_background(cell, hex_color):
    """Aplica sombreado de color a una celda de tabla en Word"""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    tc_pr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Establece márgenes internos de celda en dxa"""
    tc_pr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/><w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>')
    tc_pr.append(tcMar)

def construir_word(doc_path, imagen_erd_path, sql_script_path):
    doc = Document()

    # Configuración de márgenes estándar (1 pulgada)
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # --------------------------------------------------------------------------
    # PORTADA / ENCABEZADO PRINCIPAL
    # --------------------------------------------------------------------------
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(10)
    title_p.paragraph_format.space_after = Pt(4)
    title_run = title_p.add_run("INFORME DE BASE DE DATOS")
    title_run.font.name = "Segoe UI"
    title_run.font.size = Pt(24)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(167, 29, 29) # Rojo Safari

    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(20)
    sub_run = sub_p.add_run("Modelo Relacional Lógico y Modelo Físico DDL - Sistema Gastronómico Parque Safari")
    sub_run.font.name = "Segoe UI"
    sub_run.font.size = Pt(13)
    sub_run.font.color.rgb = RGBColor(71, 85, 105)

    # Bloque de metadatos del estudiante / proyecto
    meta_table = doc.add_table(rows=3, cols=2)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_data = [
        ("Proyecto:", "Sistema de Gestión y Venta Gastronómica (Parque Safari)"),
        ("Asignatura / Entrega:", "Proyecto Integrado - Modelo de Datos y Evidencia DDL"),
        ("Fecha:", "Octubre 2026 | Versión Oficial 1.0"),
    ]
    for row_idx, (k, v) in enumerate(meta_data):
        cell_k, cell_v = meta_table.rows[row_idx].cells
        cell_k.width = Inches(2.2)
        cell_v.width = Inches(4.3)
        p_k = cell_k.paragraphs[0]
        r_k = p_k.add_run(k)
        r_k.bold = True
        r_k.font.color.rgb = RGBColor(30, 41, 59)
        p_v = cell_v.paragraphs[0]
        p_v.add_run(v)
        set_cell_background(cell_k, "F1F5F9")
        set_cell_background(cell_v, "FFFFFF")
        set_cell_margins(cell_k, top=60, bottom=60, left=100, right=100)
        set_cell_margins(cell_v, top=60, bottom=60, left=100, right=100)

    doc.add_paragraph().paragraph_format.space_after = Pt(14)

    # --------------------------------------------------------------------------
    # SECCIÓN 1: INTRODUCCIÓN Y METODOLOGÍA
    # --------------------------------------------------------------------------
    h1 = doc.add_heading(level=1)
    r1 = h1.add_run("1. Introducción y Metodología de Diseño")
    r1.font.color.rgb = RGBColor(167, 29, 29)

    p_intro = doc.add_paragraph(
        "El presente documento detalla la arquitectura de persistencia para el Sistema Gastronómico de Parque Safari. "
        "El modelo fue diseñado bajo el paradigma relacional y normalizado hasta la Tercera Forma Normal (3NF), asegurando la "
        "consistencia de las transacciones, la ausencia de redundancias y la correcta integridad referencial entre puntos de venta, "
        "jornadas operativas, cajas, inventario de productos, mesas y derivación de pedidos a cocina y barra."
    )
    p_intro.paragraph_format.line_spacing = 1.15
    p_intro.paragraph_format.space_after = Pt(12)

    # --------------------------------------------------------------------------
    # SECCIÓN 2: MODELO RELACIONAL (DIAGRAMA ERD)
    # --------------------------------------------------------------------------
    h2 = doc.add_heading(level=1)
    r2 = h2.add_run("2. Modelo Relacional Lógico (Diagrama ERD)")
    r2.font.color.rgb = RGBColor(167, 29, 29)

    p_erd_desc = doc.add_paragraph(
        "A continuación se presenta el Diagrama Entidad-Relación (ERD) que modela las clases de negocio, sus atributos "
        "primarios (PK), claves foráneas (FK) y la cardinalidad de sus relaciones. Este diagrama sirve como base para su diagramación "
        "formal en herramientas como Draw.io."
    )
    p_erd_desc.paragraph_format.line_spacing = 1.15
    p_erd_desc.paragraph_format.space_after = Pt(10)

    # Insertar Imagen del Diagrama ERD
    if os.path.exists(imagen_erd_path):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_img = p_img.add_run()
        run_img.add_picture(imagen_erd_path, width=Inches(6.5))

        p_caption = doc.add_paragraph()
        p_caption.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_cap = p_caption.add_run("Figura 1: Diagrama Entidad-Relación Lógico en Tercera Forma Normal (3NF) - Parque Safari.")
        r_cap.font.size = Pt(9)
        r_cap.font.italic = True
        r_cap.font.color.rgb = RGBColor(100, 116, 139)
        p_caption.paragraph_format.space_after = Pt(16)

    # --------------------------------------------------------------------------
    # SECCIÓN 3: DICCIONARIO DE CLASES Y ATRIBUTOS
    # --------------------------------------------------------------------------
    h3 = doc.add_heading(level=1)
    r3 = h3.add_run("3. Diccionario de Clases / Tablas del Modelo")
    r3.font.color.rgb = RGBColor(167, 29, 29)

    entidades_dict = [
        ("punto_venta", "Locales gastronómicos físicos del parque (Restaurante Central, Cafetería La Selva, Oasis)", [
            ("id", "SERIAL", "PK", "Identificador único secuencial"),
            ("nombre", "VARCHAR(100)", "UNIQUE, NOT NULL", "Nombre oficial del local"),
            ("tipo", "VARCHAR(50)", "NULLABLE", "Restaurante, Cafetería, Kiosco"),
            ("descripcion", "TEXT", "NULLABLE", "Descripción de la oferta gastronómica"),
            ("icono", "VARCHAR(50)", "DEFAULT 'bi-shop'", "Clase de ícono Bootstrap"),
            ("color", "VARCHAR(20)", "DEFAULT '#c62828'", "Color distintivo visual hex"),
            ("activo", "BOOLEAN", "DEFAULT TRUE", "Estado operativo del punto de venta")
        ]),
        ("perfil_empleado", "Extensión de usuario con rol y restricción de puesto único de trabajo", [
            ("id", "SERIAL", "PK", "Identificador del perfil"),
            ("usuario_id", "INT", "FK -> auth_user.id, UNIQUE", "Vínculo 1 a 1 con usuario Django"),
            ("rol", "VARCHAR(20)", "CHECK IN ('ADMINISTRADOR', 'CAJERO', 'MESERO')", "Rol de acceso"),
            ("rut", "VARCHAR(12)", "NULLABLE", "RUT con formato chileno"),
            ("punto_venta_actual_id", "INT", "FK -> punto_venta.id (NULLABLE)", "Puesto de trabajo actual"),
            ("activo", "BOOLEAN", "DEFAULT TRUE", "Habilitación de acceso del colaborador")
        ]),
        ("jornada", "Ciclo operativo diario de Parque Safari para control de turnos", [
            ("id", "SERIAL", "PK", "Identificador de la jornada"),
            ("fecha", "DATE", "NOT NULL, DEFAULT CURRENT_DATE", "Fecha de operación"),
            ("fecha_hora_apertura", "TIMESTAMP", "NOT NULL", "Instante de habilitación"),
            ("fecha_hora_cierre", "TIMESTAMP", "NULLABLE", "Instante de cierre de jornada"),
            ("estado", "VARCHAR(15)", "CHECK IN ('ABIERTA', 'CERRADA')", "Estado de la jornada"),
            ("usuario_apertura_id", "INT", "FK -> auth_user.id", "Responsable de apertura")
        ]),
        ("caja", "Cajas registradoras individuales asignadas por cajero y jornada", [
            ("id", "SERIAL", "PK", "Identificador de caja"),
            ("nombre", "VARCHAR(50)", "NOT NULL", "Ej: Caja Restaurante - Carlos"),
            ("punto_venta_id", "INT", "FK -> punto_venta.id", "Local físico donde opera"),
            ("jornada_id", "INT", "FK -> jornada.id", "Jornada del día a la que pertenece"),
            ("cajero_id", "INT", "FK -> auth_user.id", "Cajero titular"),
            ("monto_apertura", "DECIMAL(10,2)", "DEFAULT 0.00", "Fondo inicial de sencillo"),
            ("estado", "VARCHAR(15)", "CHECK IN ('ABIERTA', 'CERRADA')", "Estado operativo"),
            ("CONSTRAINT", "UNIQUE(jornada_id, cajero_id)", "RESTRICCIÓN", "Máximo 1 caja por cajero al día")
        ]),
        ("mesa", "Mesas de atención para servicio en salón o terraza", [
            ("id", "SERIAL", "PK", "Identificador numérico"),
            ("identificador", "VARCHAR(20)", "NOT NULL", "Ej: Mesa 1, Terraza 3"),
            ("punto_venta_id", "INT", "FK -> punto_venta.id", "Local al que pertenece"),
            ("capacidad", "INT", "DEFAULT 4", "Número de comensales"),
            ("estado", "VARCHAR(20)", "CHECK IN ('HABILITADA', 'OCUPADA', ...)", "Estado actual"),
            ("CONSTRAINT", "UNIQUE(identificador, punto_venta_id)", "RESTRICCIÓN", "Sin mesas repetidas por local")
        ]),
        ("producto", "Alimentos, bebidas y preparaciones disponibles", [
            ("id", "SERIAL", "PK", "Identificador del producto"),
            ("nombre", "VARCHAR(150)", "NOT NULL", "Nombre comercial del alimento"),
            ("categoria_id", "INT", "FK -> categoria.id", "Categoría gastronómica"),
            ("precio_base", "DECIMAL(10,2)", "NOT NULL", "Precio base en pesos chilenos"),
            ("descripcion", "TEXT", "NULLABLE", "Ingredientes y descripción"),
            ("activo", "BOOLEAN", "DEFAULT TRUE", "Disponibilidad en carta")
        ]),
        ("venta", "Registro de transacción económica y cobro", [
            ("id", "SERIAL", "PK", "Número de venta"),
            ("caja_id", "INT", "FK -> caja.id", "Caja que recauda"),
            ("cajero_id", "INT", "FK -> auth_user.id", "Operador que efectúa el cobro"),
            ("punto_venta_id", "INT", "FK -> punto_venta.id", "Local donde se produce la venta"),
            ("mesa_id", "INT", "FK -> mesa.id (NULLABLE)", "Mesa asociada (si aplica)"),
            ("modalidad", "VARCHAR(20)", "CHECK IN ('VENTA_RAPIDA', 'MESA')", "Formato de atención"),
            ("metodo_pago", "VARCHAR(20)", "CHECK IN ('EFECTIVO', 'DEBITO', ...)", "Medio de pago"),
            ("total", "DECIMAL(12,2)", "NOT NULL", "Monto total transaccionado en CLP")
        ]),
        ("detalle_pedido", "Desglose de comanda con soporte de observaciones libres", [
            ("id", "SERIAL", "PK", "Identificador de línea"),
            ("pedido_id", "INT", "FK -> pedido.id", "Comanda asociada"),
            ("producto_id", "INT", "FK -> producto.id", "Producto solicitado"),
            ("cantidad", "INT", "DEFAULT 1", "Unidades pedidas"),
            ("observaciones", "VARCHAR(200)", "NULLABLE", "Nota libre: sin cebolla, sin sal, etc.")
        ]),
        ("ticket", "Emisión atómica e independiente para Cocina y Barra", [
            ("id", "SERIAL", "PK", "Identificador del ticket"),
            ("pedido_id", "INT", "FK -> pedido.id", "Pedido que lo origina"),
            ("codigo", "VARCHAR(30)", "UNIQUE", "Código térmico (COM-COC-0001, COM-BAR-0001)"),
            ("tipo_destino", "VARCHAR(20)", "CHECK IN ('COCINA', 'BARRA', ...)", "Destino físico"),
            ("estado", "VARCHAR(20)", "CHECK IN ('EMITIDO', 'EN_PROCESO', ...)", "Estado de producción")
        ])
    ]

    for tabla_nombre, tabla_desc, columnas in entidades_dict:
        h_tbl = doc.add_heading(level=2)
        r_tbl = h_tbl.add_run(f"Tabla: {tabla_nombre}")
        r_tbl.font.color.rgb = RGBColor(30, 41, 59)

        p_desc = doc.add_paragraph(tabla_desc)
        p_desc.paragraph_format.space_after = Pt(4)

        t = doc.add_table(rows=1 + len(columnas), cols=4)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        headers = ["Columna / Atributo", "Tipo de Dato", "Restricción / Key", "Descripción"]
        
        # Formato cabecera de tabla
        for col_idx, h_text in enumerate(headers):
            cell = t.rows[0].cells[col_idx]
            cell.text = h_text
            p = cell.paragraphs[0]
            p.runs[0].bold = True
            p.runs[0].font.color.rgb = RGBColor(255, 255, 255)
            p.runs[0].font.size = Pt(8.5)
            set_cell_background(cell, "1E3A8A")
            set_cell_margins(cell, top=60, bottom=60, left=80, right=80)

        # Rellenar filas
        for row_idx, (col_nom, col_tipo, col_key, col_obs) in enumerate(columnas, start=1):
            row = t.rows[row_idx]
            row.cells[0].text = col_nom
            row.cells[1].text = col_tipo
            row.cells[2].text = col_key
            row.cells[3].text = col_obs
            bg_col = "F8FAFC" if (row_idx % 2 == 0) else "FFFFFF"
            for c_i in range(4):
                c = row.cells[c_i]
                set_cell_background(c, bg_col)
                set_cell_margins(c, top=45, bottom=45, left=80, right=80)
                p_c = c.paragraphs[0]
                p_c.runs[0].font.size = Pt(8.0)
                p_c.runs[0].font.color.rgb = RGBColor(30, 41, 59)
                if c_i == 0 and "PK" in col_key:
                    p_c.runs[0].bold = True

        doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # --------------------------------------------------------------------------
    # SECCIÓN 4: MODELO FÍSICO (SCRIPT DDL DE BASE DE DATOS)
    # --------------------------------------------------------------------------
    doc.add_page_break()
    h4 = doc.add_heading(level=1)
    r4 = h4.add_run("4. Modelo Físico (Script de Base de Datos - DDL)")
    r4.font.color.rgb = RGBColor(167, 29, 29)

    p_sql_desc = doc.add_paragraph(
        "Corresponde a la codificación de las instrucciones del modelo relacional generado previamente, "
        "es decir, sentencias 'CREATE TABLE', representando correctamente las relaciones, claves primarias, claves foráneas "
        "y reglas declaradas en la diagramación (adjuntar como evidencia)."
    )
    p_sql_desc.paragraph_format.line_spacing = 1.15
    p_sql_desc.paragraph_format.space_after = Pt(12)

    # Leer el script SQL completo y formatearlo en bloque de código
    if os.path.exists(sql_script_path):
        with open(sql_script_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # Crear bloque con estilo de código
        sql_table = doc.add_table(rows=1, cols=1)
        sql_table.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell_sql = sql_table.rows[0].cells[0]
        cell_sql.width = Inches(6.5)
        set_cell_background(cell_sql, "F1F5F9")
        set_cell_margins(cell_sql, top=120, bottom=120, left=150, right=150)

        p_sql = cell_sql.paragraphs[0]
        p_sql.paragraph_format.line_spacing = 1.05
        p_sql.paragraph_format.space_before = Pt(2)
        p_sql.paragraph_format.space_after = Pt(2)

        r_sql = p_sql.add_run(sql_content)
        r_sql.font.name = "Consolas"
        r_sql.font.size = Pt(8.0)
        r_sql.font.color.rgb = RGBColor(15, 23, 42)

    # --------------------------------------------------------------------------
    # SECCIÓN 5: REGLAS DE INTEGRIDAD Y RESTRICCIONES
    # --------------------------------------------------------------------------
    doc.add_paragraph().paragraph_format.space_after = Pt(14)
    h5 = doc.add_heading(level=1)
    r5 = h5.add_run("5. Reglas de Integridad y Restricciones del Negocio")
    r5.font.color.rgb = RGBColor(167, 29, 29)

    reglas = [
        ("Puesto Único de Trabajo (RF01 / RF04):",
         "Cada colaborador solo puede tener asignado un punto de venta a la vez a través de 'perfil_empleado.punto_venta_actual_id'. Cualquier reasignación genera un registro histórico en 'alerta_traslado'."),
        ("Caja Única por Turno (RF03):",
         "Se garantiza a nivel de motor mediante 'CONSTRAINT uq_caja_cajero_jornada UNIQUE (jornada_id, cajero_id)' que un cajero no pueda abrir más de una caja activa en la misma jornada."),
        ("Identificador de Mesa Único por Local (RF06):",
         "La restricción 'UNIQUE (identificador, punto_venta_id)' permite reutilizar números comunes (ej: 'Mesa 1') entre distintos restaurantes sin generar colisiones."),
        ("Persistencia Atómica y Desacoplamiento de Comandas (RF09 / RF10):",
         "Al despachar una comanda, se persisten atómicamente 'Venta', 'DetalleVenta', 'Pedido', 'DetallePedido' y se generan independientemente los tickets 'COM-COC-XXXX' y 'COM-BAR-XXXX' según el destino de los productos."),
        ("Soporte de Notas Libres de Preparación:",
         "El campo 'detalle_pedido.observaciones' almacena indicaciones libres y personalizadas del comensal (ej: 'sin queso cheddar', 'sin sal') sin requerir etiquetas rígidas predefinidas."),
        ("Protección ante Eliminación Accidental:",
         "Las relaciones críticas hacia ventas, cajas y consumos implementan 'ON DELETE RESTRICT' / 'PROTECT'. Si un administrador elimina un local con ventas registradas, el sistema captura la excepción y aplica una desactivación lógica ('activo = FALSE'), garantizando la auditoría histórica.")
    ]

    for reg_tit, reg_txt in reglas:
        p_reg = doc.add_paragraph()
        p_reg.paragraph_format.left_indent = Inches(0.2)
        p_reg.paragraph_format.space_after = Pt(6)
        r_tit = p_reg.add_run(f"• {reg_tit} ")
        r_tit.bold = True
        r_tit.font.color.rgb = RGBColor(30, 41, 59)
        r_txt = p_reg.add_run(reg_txt)
        r_txt.font.color.rgb = RGBColor(71, 85, 105)

    doc.save(doc_path)
    print(f"[+] Documento Word generado exitosamente en: {doc_path}")

if __name__ == '__main__':
    base_dir = r"c:\Users\pc\Desktop\safari Pilar"
    desktop_dir = r"c:\Users\pc\Desktop"

    img_path = os.path.join(base_dir, "diagrama_erd_parque_safari.png")
    sql_path = os.path.join(base_dir, "modelo_fisico_safari.sql")
    word_project_path = os.path.join(base_dir, "Informe_Modelo_Base_de_Datos_Parque_Safari.docx")
    word_desktop_path = os.path.join(desktop_dir, "Informe_Modelo_Base_de_Datos_Parque_Safari.docx")

    # 1. Generar Imagen ERD
    generar_imagen_erd(img_path)

    # 2. Generar Documento Word en Proyecto
    construir_word(word_project_path, img_path, sql_path)

    # 3. Guardar copia en Escritorio para acceso directo
    construir_word(word_desktop_path, img_path, sql_path)
    print("[OK] Proceso completado al 100%. Documentos generados con exito.")
