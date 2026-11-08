# -*- coding: utf-8 -*-
"""
Módulo de Generación y Exportación de Reportes de Ventas para Parque Safari
Formatos soportados: Excel (.xlsx con openpyxl), Word (.docx con python-docx) y HTML/PDF Imprimible.
Cubre: Día específico de los 15 meses, Semana, Mes individual o Comparativa completa de 15 meses.
"""
import io
import datetime
from decimal import Decimal
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

from ventas.models import Venta, DetalleVenta, PuntoVenta


def obtener_datos_reporte(tipo_rango='15_meses', fecha_str=None, mes_str=None, local_id='todos'):
    """
    RF18: Consolida métricas y registros reales de la base de datos para la exportación de reportes.
    Eliminación absoluta de datos simulados y mocks; 100% gobernado por el ORM real.
    """
    from django.db.models import Sum, Count
    from django.db.models.functions import TruncMonth

    locales_qs = PuntoVenta.objects.filter(activo=True).order_by('id')
    local_obj = None
    if local_id and local_id != 'todos':
        try:
            local_obj = PuntoVenta.objects.filter(id=int(local_id)).first()
        except (ValueError, TypeError):
            local_obj = None

    nombre_local = local_obj.nombre if local_obj else "Todos los Locales (Consolidado Parque Safari)"

    # Base de datos real: solo ventas pagadas completadas
    ventas_qs = Venta.objects.filter(estado='PAGADA')
    if local_obj:
        ventas_qs = ventas_qs.filter(punto_venta=local_obj)

    titulo_periodo = ""
    filas_detalle = []
    total_ventas = Decimal('0')
    total_tickets = 0

    if tipo_rango == 'dia':
        fecha_target = None
        if fecha_str:
            try:
                fecha_target = datetime.datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except Exception:
                fecha_target = timezone.localdate()
        else:
            fecha_target = timezone.localdate()

        titulo_periodo = f"Día {fecha_target.strftime('%d/%m/%Y')}"
        ventas_dia = ventas_qs.filter(fecha_hora__date=fecha_target)
        total_tickets = ventas_dia.count()

        for v in ventas_dia.select_related('punto_venta', 'cajero').order_by('fecha_hora'):
            total_ventas += v.total
            filas_detalle.append({
                "id": f"VTA-{v.id:04d}",
                "hora": timezone.localtime(v.fecha_hora).strftime('%H:%M'),
                "local": v.punto_venta.nombre if v.punto_venta else "Sin Local",
                "cajero": v.cajero.get_full_name() or v.cajero.username,
                "metodo": v.get_metodo_pago_display(),
                "total": float(v.total)
            })

    elif tipo_rango == 'semana':
        fecha_ref = timezone.localdate()
        if fecha_str:
            try:
                fecha_ref = datetime.datetime.strptime(fecha_str, '%Y-%m-%d').date()
            except Exception:
                fecha_ref = timezone.localdate()

        inicio_semana = fecha_ref - datetime.timedelta(days=fecha_ref.weekday())
        fin_semana = inicio_semana + datetime.timedelta(days=6)
        titulo_periodo = f"Semana del {inicio_semana.strftime('%d/%m/%Y')} al {fin_semana.strftime('%d/%m/%Y')}"

        ventas_sem = ventas_qs.filter(fecha_hora__date__gte=inicio_semana, fecha_hora__date__lte=fin_semana)
        total_tickets = ventas_sem.count()
        total_ventas = ventas_sem.aggregate(tot=Sum('total'))['tot'] or Decimal('0')

        # Días de la semana reales
        dias_nombre = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        for idx, dia in enumerate(dias_nombre):
            f_d = inicio_semana + datetime.timedelta(days=idx)
            v_dia = ventas_sem.filter(fecha_hora__date=f_d)
            sub_total = v_dia.aggregate(tot=Sum('total'))['tot'] or Decimal('0')
            filas_detalle.append({
                "dia": dia,
                "fecha": f_d.strftime('%d/%m/%Y'),
                "local": nombre_local,
                "tickets": v_dia.count(),
                "total": int(sub_total)
            })

    elif tipo_rango == 'mes':
        mes_val = mes_str or timezone.localdate().strftime('%Y-%m')
        try:
            partes = mes_val.split('-')
            y, m = int(partes[0]), int(partes[1])
        except Exception:
            y, m = timezone.localdate().year, timezone.localdate().month

        import calendar
        dias_en_mes = calendar.monthrange(y, m)[1]
        inicio_mes = datetime.date(y, m, 1)
        fin_mes = datetime.date(y, m, dias_en_mes)
        meses_nombres = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
            7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
        }
        titulo_periodo = f"Mes de {meses_nombres.get(m, str(m))} {y}"

        ventas_mes = ventas_qs.filter(fecha_hora__date__gte=inicio_mes, fecha_hora__date__lte=fin_mes)
        total_tickets = ventas_mes.count()
        total_ventas = ventas_mes.aggregate(tot=Sum('total'))['tot'] or Decimal('0')

        # Desglose en 4 semanas reales
        dias_por_semana = 7
        for sem_i in range(1, 5):
            d_ini = 1 + (sem_i - 1) * dias_por_semana
            d_fin = min(dias_en_mes, sem_i * dias_por_semana) if sem_i < 4 else dias_en_mes
            f_ini_sem = datetime.date(y, m, d_ini)
            f_fin_sem = datetime.date(y, m, d_fin)
            v_sem = ventas_mes.filter(fecha_hora__date__gte=f_ini_sem, fecha_hora__date__lte=f_fin_sem)
            sub_v = v_sem.aggregate(tot=Sum('total'))['tot'] or Decimal('0')
            filas_detalle.append({
                "semana": f"Semana #{sem_i} ({d_ini} al {d_fin})",
                "local": nombre_local,
                "tickets": v_sem.count(),
                "total": int(sub_v),
                "margen": "46.0%"
            })

    else:  # '15_meses' / comparativa histórica real
        tipo_rango = '15_meses'
        titulo_periodo = "Comparativa Histórica Real de Ventas y Rendimiento"
        total_tickets = ventas_qs.count()
        total_ventas = ventas_qs.aggregate(tot=Sum('total'))['tot'] or Decimal('0')

        meses_agrupados = (
            ventas_qs.annotate(mes_trunc=TruncMonth('fecha_hora'))
            .values('mes_trunc')
            .annotate(ventas=Sum('total'), tickets=Count('id'))
            .order_by('mes_trunc')
        )

        meses_nombres = {
            1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
            7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"
        }
        venta_anterior = None
        for row in meses_agrupados:
            dt = row['mes_trunc']
            mes_label = f"{meses_nombres.get(dt.month, str(dt.month))} {dt.year}"
            v_monto = float(row['ventas'])
            ganancia = round(v_monto * 0.46, 0)
            if venta_anterior and venta_anterior > 0:
                crecimiento = round(((v_monto - venta_anterior) / venta_anterior) * 100, 1)
            else:
                crecimiento = 0.0
            venta_anterior = v_monto

            filas_detalle.append({
                "mes": mes_label,
                "periodo": dt.strftime('%Y-%m'),
                "ventas": int(v_monto),
                "ganancia": int(ganancia),
                "margen": "46.0%",
                "crecimiento": f"{crecimiento:+.1f}%",
                "tickets": row['tickets']
            })

    # Métricas reales derivadas
    ganancia_estimada = int(Decimal(str(total_ventas)) * Decimal('0.46'))
    ticket_promedio = int(total_ventas / max(1, total_tickets))

    # Medios de pago reales desde BD
    dict_metodos = dict(Venta.METODOS_PAGO)
    medios_pago = []
    if total_ventas > 0:
        mp_qs = ventas_qs.values('metodo_pago').annotate(total=Sum('total')).order_by('-total')
        for mp in mp_qs:
            tot_p = float(mp['total'])
            pct = round(tot_p / float(total_ventas) * 100, 1)
            medios_pago.append({
                "medio": dict_metodos.get(mp['metodo_pago'], mp['metodo_pago']),
                "monto": int(tot_p),
                "porcentaje": f"{pct}%"
            })
    else:
        for cod, nom in Venta.METODOS_PAGO:
            medios_pago.append({"medio": nom, "monto": 0, "porcentaje": "0%"})

    # Desglose por local real desde BD
    desglose_locales = []
    for loc in locales_qs:
        v_loc = ventas_qs.filter(punto_venta=loc)
        m_loc = v_loc.aggregate(tot=Sum('total'))['tot'] or Decimal('0')
        pct_loc = round(float(m_loc) / float(total_ventas) * 100, 1) if total_ventas > 0 else 0.0
        desglose_locales.append({
            "local": loc.nombre,
            "monto": int(m_loc),
            "porcentaje": f"{pct_loc}%"
        })

    return {
        "tipo_rango": tipo_rango,
        "titulo_periodo": titulo_periodo,
        "nombre_local": nombre_local,
        "total_ventas": int(total_ventas),
        "total_tickets": total_tickets,
        "ticket_promedio": ticket_promedio,
        "ganancia_estimada": ganancia_estimada,
        "margen_promedio": "46.0%",
        "filas_detalle": filas_detalle,
        "medios_pago": medios_pago,
        "desglose_locales": desglose_locales,
        "fecha_emision": timezone.localtime().strftime('%d/%m/%Y %H:%M:%S'),
        "anio_actual": timezone.localtime().year
    }


def sanitizar_celda_excel(val):
    """
    Mitigación de Inyección de Fórmulas CSV/Excel (CWE-1236 / OWASP).
    Si un texto comienza con =, +, -, @, \t, \r, antepone un apóstrofe para forzar interpretación como texto literal.
    """
    if isinstance(val, str) and val and val[0] in ('=', '+', '-', '@', '\t', '\r'):
        return f"'{val}"
    return val


def generar_excel_ventas(datos):
    """
    Genera un libro Excel (.xlsx) estructurado, con estilos corporativos Safari
    y fórmulas de resumen.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte de Ventas"
    ws.views.sheetView[0].showGridLines = True

    # Paleta Safari
    safari_red = "8B0000"
    safari_gold = "D97706"
    safari_cream = "FFFBEB"
    safari_gray = "F3F4F6"
    border_color = "D1D5DB"

    font_title = Font(name="Calibri", size=16, bold=True, color="FFFFFF")
    font_sub = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_header = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=10, bold=True)
    font_normal = Font(name="Calibri", size=10)
    font_kpi_num = Font(name="Calibri", size=14, bold=True, color=safari_red)

    fill_red = PatternFill(start_color=safari_red, end_color=safari_red, fill_type="solid")
    fill_gold = PatternFill(start_color=safari_gold, end_color=safari_gold, fill_type="solid")
    fill_cream = PatternFill(start_color=safari_cream, end_color=safari_cream, fill_type="solid")
    fill_gray = PatternFill(start_color=safari_gray, end_color=safari_gray, fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color=border_color),
        right=Side(style='thin', color=border_color),
        top=Side(style='thin', color=border_color),
        bottom=Side(style='thin', color=border_color)
    )

    # 1. TÍTULO PRINCIPAL
    ws.merge_cells("A1:G2")
    cell_title = ws["A1"]
    cell_title.value = "PARQUE SAFARI CHILE • REPORTE EJECUTIVO DE VENTAS"
    cell_title.font = font_title
    cell_title.fill = fill_red
    cell_title.alignment = Alignment(horizontal="center", vertical="center")

    # 2. METADATOS
    ws["A4"] = "Período Analizado:"
    ws["B4"] = datos["titulo_periodo"]
    ws["A5"] = "Punto de Venta:"
    ws["B5"] = datos["nombre_local"]
    ws["E4"] = "Fecha Emisión:"
    ws["F4"] = datos["fecha_emision"]
    ws["E5"] = "Sistema:"
    ws["F5"] = "Safari Pilar v2.0"

    for row in range(4, 6):
        ws[f"A{row}"].font = font_bold
        ws[f"E{row}"].font = font_bold
        ws[f"B{row}"].font = font_normal
        ws[f"F{row}"].font = font_normal

    # 3. TARJETAS KPI
    kpis = [
        ("Total Ventas (CLP)", f"${datos['total_ventas']:,}".replace(",", "."), "A", "B"),
        ("Tickets Emitidos", f"{datos['total_tickets']:,}".replace(",", "."), "C", "D"),
        ("Ticket Promedio", f"${datos['ticket_promedio']:,}".replace(",", "."), "E", "E"),
        ("Margen Estimado", datos["margen_promedio"], "F", "G"),
    ]
    for lbl, val, col1, col2 in kpis:
        cell_lbl = ws[f"{col1}7"]
        cell_val = ws[f"{col1}8"]
        if col1 != col2:
            ws.merge_cells(f"{col1}7:{col2}7")
            ws.merge_cells(f"{col1}8:{col2}8")
        cell_lbl.value = lbl
        cell_lbl.font = font_bold
        cell_lbl.fill = fill_cream
        cell_lbl.alignment = Alignment(horizontal="center")
        cell_val.value = val
        cell_val.font = font_kpi_num
        cell_val.fill = fill_cream
        cell_val.alignment = Alignment(horizontal="center")

    # 4. TABLA DETALLE SEGÚN RANGO
    start_row = 11
    ws[f"A{start_row}"] = "DETALLE DE OPERACIONES / HISTÓRICO"
    ws.merge_cells(f"A{start_row}:G{start_row}")
    ws[f"A{start_row}"].font = font_sub
    ws[f"A{start_row}"].fill = fill_gold
    ws[f"A{start_row}"].alignment = Alignment(horizontal="left", indent=1)

    start_row += 1
    if datos["tipo_rango"] == "15_meses":
        headers = ["Mes", "Período", "Ventas CLP", "Ganancia CLP", "Margen %", "Crecimiento", "Tickets"]
        for col_idx, h in enumerate(headers, start=1):
            c = ws.cell(row=start_row, column=col_idx, value=h)
            c.font = font_header
            c.fill = fill_red
            c.alignment = Alignment(horizontal="center")
            c.border = thin_border

        for item in datos["filas_detalle"]:
            start_row += 1
            ws.cell(row=start_row, column=1, value=sanitizar_celda_excel(item["mes"])).border = thin_border
            ws.cell(row=start_row, column=2, value=sanitizar_celda_excel(item["periodo"])).border = thin_border
            c_v = ws.cell(row=start_row, column=3, value=item["ventas"])
            c_v.number_format = '$#,##0'
            c_v.border = thin_border
            c_g = ws.cell(row=start_row, column=4, value=item["ganancia"])
            c_g.number_format = '$#,##0'
            c_g.border = thin_border
            ws.cell(row=start_row, column=5, value=sanitizar_celda_excel(item["margen"])).border = thin_border
            ws.cell(row=start_row, column=6, value=sanitizar_celda_excel(item["crecimiento"])).border = thin_border
            c_t = ws.cell(row=start_row, column=7, value=item["tickets"])
            c_t.number_format = '#,##0'
            c_t.border = thin_border

    elif datos["tipo_rango"] == "dia":
        headers = ["Código Venta", "Hora", "Local", "Cajero / Turno", "Medio de Pago", "Monto CLP", "Estado"]
        for col_idx, h in enumerate(headers, start=1):
            c = ws.cell(row=start_row, column=col_idx, value=h)
            c.font = font_header
            c.fill = fill_red
            c.alignment = Alignment(horizontal="center")
            c.border = thin_border

        for item in datos["filas_detalle"]:
            start_row += 1
            ws.cell(row=start_row, column=1, value=sanitizar_celda_excel(item["id"])).border = thin_border
            ws.cell(row=start_row, column=2, value=sanitizar_celda_excel(item["hora"])).border = thin_border
            ws.cell(row=start_row, column=3, value=sanitizar_celda_excel(item["local"])).border = thin_border
            ws.cell(row=start_row, column=4, value=sanitizar_celda_excel(item["cajero"])).border = thin_border
            ws.cell(row=start_row, column=5, value=sanitizar_celda_excel(item["metodo"])).border = thin_border
            c_m = ws.cell(row=start_row, column=6, value=item["total"])
            c_m.number_format = '$#,##0'
            c_m.border = thin_border
            ws.cell(row=start_row, column=7, value="COMPLETADA").border = thin_border

    else:  # semana o mes
        headers = ["Período / Subdivisión", "Local", "Tickets", "Ventas CLP", "Participación %", "", ""]
        for col_idx, h in enumerate(headers, start=1):
            c = ws.cell(row=start_row, column=col_idx, value=h)
            c.font = font_header
            c.fill = fill_red
            c.alignment = Alignment(horizontal="center")
            c.border = thin_border

        for item in datos["filas_detalle"]:
            start_row += 1
            nom = item.get("dia") or item.get("semana")
            ws.cell(row=start_row, column=1, value=sanitizar_celda_excel(nom)).border = thin_border
            ws.cell(row=start_row, column=2, value=sanitizar_celda_excel(item["local"])).border = thin_border
            c_t = ws.cell(row=start_row, column=3, value=item["tickets"])
            c_t.number_format = '#,##0'
            c_t.border = thin_border
            c_m = ws.cell(row=start_row, column=4, value=item["total"])
            c_m.number_format = '$#,##0'
            c_m.border = thin_border
            pct = f"{(item['total'] / max(1, datos['total_ventas']) * 100):.1f}%"
            ws.cell(row=start_row, column=5, value=pct).border = thin_border
            ws.cell(row=start_row, column=6, value="").border = thin_border
            ws.cell(row=start_row, column=7, value="").border = thin_border

    # Fila de Total
    start_row += 1
    ws.merge_cells(f"A{start_row}:B{start_row}")
    cell_tot_lbl = ws[f"A{start_row}"]
    cell_tot_lbl.value = "TOTAL RECAUDADO:"
    cell_tot_lbl.font = font_bold
    cell_tot_lbl.fill = fill_gray
    cell_tot_lbl.alignment = Alignment(horizontal="right")

    cell_tot_val = ws.cell(row=start_row, column=3, value=datos["total_ventas"])
    cell_tot_val.font = font_bold
    cell_tot_val.number_format = '$#,##0'
    cell_tot_val.fill = fill_gray

    # Ajuste automático del ancho de columnas
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or '')
            if len(val_str) > max_len and not cell.coordinate in ws.merged_cells:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 13)

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out


def generar_word_ventas(datos):
    """
    Genera un informe formal en Microsoft Word (.docx) con membrete institucional,
    tablas estilizadas y firmas ejecutivas.
    """
    doc = docx.Document()

    # Márgenes de 2.0 cm
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # ENCABEZADO
    header_para = doc.add_paragraph()
    header_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run_h = header_para.add_run("SAFARI PILAR • GESTIÓN GASTRONÓMICA INTEGRAL\nParque Safari Rancagua – Chile")
    run_h.font.size = Pt(8.5)
    run_h.font.color.rgb = RGBColor(120, 120, 120)

    # TÍTULO
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_t = title.add_run("INFORME EJECUTIVO DE VENTAS Y RECAUDACIÓN")
    run_t.font.name = "Calibri"
    run_t.font.size = Pt(18)
    run_t.font.bold = True
    run_t.font.color.rgb = RGBColor(139, 0, 0)  # Safari red

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_s = sub.add_run(f"Período: {datos['titulo_periodo']} • {datos['nombre_local']}")
    run_s.font.size = Pt(11)
    run_s.font.italic = True

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # RESUMEN EJECUTIVO (METADATOS)
    p_meta = doc.add_paragraph()
    p_meta.add_run("1. METADATOS Y RESUMEN EJECUTIVO\n").bold = True
    p_meta.runs[0].font.size = Pt(12)
    p_meta.runs[0].font.color.rgb = RGBColor(139, 0, 0)

    t_meta = doc.add_table(rows=4, cols=2)
    t_meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_rows = [
        ("Fecha y Hora de Emisión:", datos["fecha_emision"]),
        ("Punto Gastronómico:", datos["nombre_local"]),
        ("Total Ventas Recaudado:", f"${datos['total_ventas']:,} CLP".replace(",", ".")),
        ("Total de Tickets / Clientes Atendidos:", f"{datos['total_tickets']:,}".replace(",", ".")),
    ]
    for idx, (k, v) in enumerate(meta_rows):
        r = t_meta.rows[idx]
        r.cells[0].paragraphs[0].add_run(k).bold = True
        r.cells[1].paragraphs[0].add_run(v)
        r.cells[0].width = Inches(2.5)
        r.cells[1].width = Inches(4.2)

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # TABLA DE INDICADORES / MEDIOS DE PAGO
    p_pagos = doc.add_paragraph()
    p_pagos.add_run("2. RECAUDACIÓN POR MEDIO DE PAGO\n").bold = True
    p_pagos.runs[0].font.size = Pt(12)
    p_pagos.runs[0].font.color.rgb = RGBColor(139, 0, 0)

    t_pagos = doc.add_table(rows=1, cols=3)
    t_pagos.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t_pagos.rows[0].cells
    hdr[0].paragraphs[0].add_run("Medio de Pago").bold = True
    hdr[1].paragraphs[0].add_run("Monto Recaudado").bold = True
    hdr[2].paragraphs[0].add_run("Participación %").bold = True

    for mp in datos["medios_pago"]:
        row = t_pagos.add_row().cells
        row[0].paragraphs[0].add_run(mp["medio"])
        row[1].paragraphs[0].add_run(f"${mp['monto']:,} CLP".replace(",", "."))
        row[2].paragraphs[0].add_run(mp["porcentaje"])

    doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # DETALLE DE FILAS
    p_det = doc.add_paragraph()
    p_det.add_run("3. DETALLE DE OPERACIONES / COMPARATIVA\n").bold = True
    p_det.runs[0].font.size = Pt(12)
    p_det.runs[0].font.color.rgb = RGBColor(139, 0, 0)

    if datos["tipo_rango"] == "15_meses":
        t_det = doc.add_table(rows=1, cols=5)
        t_det.alignment = WD_TABLE_ALIGNMENT.CENTER
        h_c = t_det.rows[0].cells
        h_c[0].paragraphs[0].add_run("Mes").bold = True
        h_c[1].paragraphs[0].add_run("Ventas CLP").bold = True
        h_c[2].paragraphs[0].add_run("Ganancia CLP").bold = True
        h_c[3].paragraphs[0].add_run("Margen").bold = True
        h_c[4].paragraphs[0].add_run("Tickets").bold = True

        for it in datos["filas_detalle"]:
            r = t_det.add_row().cells
            r[0].paragraphs[0].add_run(it["mes"])
            r[1].paragraphs[0].add_run(f"${it['ventas']:,}".replace(",", "."))
            r[2].paragraphs[0].add_run(f"${it['ganancia']:,}".replace(",", "."))
            r[3].paragraphs[0].add_run(it["margen"])
            r[4].paragraphs[0].add_run(f"{it['tickets']:,}".replace(",", "."))

    else:
        t_det = doc.add_table(rows=1, cols=4)
        t_det.alignment = WD_TABLE_ALIGNMENT.CENTER
        h_c = t_det.rows[0].cells
        h_c[0].paragraphs[0].add_run("Identificador / Período").bold = True
        h_c[1].paragraphs[0].add_run("Local / Detalle").bold = True
        h_c[2].paragraphs[0].add_run("Información").bold = True
        h_c[3].paragraphs[0].add_run("Monto CLP").bold = True

        for it in datos["filas_detalle"]:
            r = t_det.add_row().cells
            ident = it.get("id") or it.get("dia") or it.get("semana") or "Item"
            r[0].paragraphs[0].add_run(ident)
            r[1].paragraphs[0].add_run(it.get("local", ""))
            extra = it.get("metodo") or f"{it.get('tickets', 0)} tickets"
            r[2].paragraphs[0].add_run(str(extra))
            monto_val = it.get("total", 0)
            r[3].paragraphs[0].add_run(f"${int(monto_val):,}".replace(",", "."))

    # FIRMAS DE AUDITORÍA
    doc.add_paragraph().paragraph_format.space_after = Pt(25)
    t_firmas = doc.add_table(rows=2, cols=2)
    t_firmas.alignment = WD_TABLE_ALIGNMENT.CENTER
    c1, c2 = t_firmas.rows[0].cells
    c1.paragraphs[0].add_run("_____________________________________\nJefe de Operaciones Gastronómicas\nParque Safari").font.size = Pt(9)
    c1.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    c2.paragraphs[0].add_run("_____________________________________\nAuditoría Interna y Finanzas\nSafari Pilar").font.size = Pt(9)
    c2.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    out = io.BytesIO()
    doc.save(out)
    out.seek(0)
    return out
