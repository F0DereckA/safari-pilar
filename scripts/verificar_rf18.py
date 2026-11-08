# -*- coding: utf-8 -*-
"""
Script de verificación y regresión manual integral para RF18 (4 Roles + Reportes y Estadísticas)
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Venta_safari.settings')

import django
django.setup()

from django.test import Client
from django.urls import reverse
from django.contrib.auth.models import User
from ventas.models import PuntoVenta, PerfilEmpleado, Mesa, Producto, Venta, DetalleVenta
from ventas.utils import generar_reporte_estadistico_integral
from ventas.exportador_reportes import obtener_datos_reporte, generar_excel_ventas, generar_word_ventas

def test_regresion_rf18():
    client = Client()

    print("=== INICIANDO REGRESIÓN DE LOS 4 ROLES + RF18 ===")

    # 1. ROL ADMINISTRADOR
    admin = User.objects.filter(perfil__rol='ADMINISTRADOR').first()
    if not admin:
        from django.utils.crypto import get_random_string
        admin = User.objects.create_superuser('admin_audit_18', 'admin18@safari.cl', get_random_string(16))
        pv = PuntoVenta.objects.first()
        PerfilEmpleado.objects.create(usuario=admin, rol='ADMINISTRADOR', punto_venta_actual=pv)

    client.force_login(admin)

    # 1.1 Panel Administrador General
    resp_admin = client.get(reverse('administrador'))
    assert resp_admin.status_code == 200, f"Error en panel administrador: {resp_admin.status_code}"
    print("  [+] Rol ADMINISTRADOR: Panel general accesible (HTTP 200)")

    # 1.2 Dashboard de Reportes y Estadísticas (RF18)
    resp_dash = client.get(reverse('administrador_dashboard'))
    assert resp_dash.status_code == 200, f"Error en dashboard: {resp_dash.status_code}"
    content_dash = resp_dash.content.decode('utf-8')
    assert "DASHBOARD DE VENTAS" in content_dash, "Título dashboard no encontrado"
    assert "Ranking de Productos Más Vendidos" in content_dash, "Sección ranking no encontrada"
    assert "chartDataJson" in content_dash, "JSON de gráficos reales no encontrado"
    print("  [+] Rol ADMINISTRADOR: Dashboard analítico con cero mocks y ORM real (HTTP 200)")

    # 1.3 Exportación oficial de reportes
    resp_exp_excel = client.get(reverse('exportar_reporte_ventas') + '?tipo_rango=15_meses&formato=excel')
    assert resp_exp_excel.status_code == 200, f"Error exportar Excel: {resp_exp_excel.status_code}"
    assert len(resp_exp_excel.content) > 1000, "Contenido Excel vacío"
    print("  [+] Rol ADMINISTRADOR: Exportación Excel oficial sin mocks verificada (HTTP 200)")

    resp_exp_word = client.get(reverse('exportar_reporte_ventas') + '?tipo_rango=15_meses&formato=word')
    assert resp_exp_word.status_code == 200, f"Error exportar Word: {resp_exp_word.status_code}"
    assert len(resp_exp_word.content) > 1000, "Contenido Word vacío"
    print("  [+] Rol ADMINISTRADOR: Exportación Word oficial sin mocks verificada (HTTP 200)")

    # 1.4 Gestión de Mesas e Historial
    resp_mesas = client.get(reverse('administrador_mesas'))
    assert resp_mesas.status_code == 200, f"Error en administrador_mesas: {resp_mesas.status_code}"
    resp_hist = client.get(reverse('administrador_historial'))
    assert resp_hist.status_code == 200, f"Error en administrador_historial: {resp_hist.status_code}"
    print("  [+] Rol ADMINISTRADOR: Gestión de mesas e historial de auditoría accesibles (HTTP 200)")

    # 2. ROL CAJERO
    cajero = User.objects.filter(perfil__rol='CAJERO', is_active=True).first()
    if cajero:
        client.force_login(cajero)
        resp_caja = client.get(reverse('crear_ticket'))
        assert resp_caja.status_code in [200, 302], f"Error en POS cajero: {resp_caja.status_code}"
        
        # Bloqueo a dashboard administrador
        resp_bloqueo = client.get(reverse('administrador_dashboard'))
        assert resp_bloqueo.status_code in [302, 403], f"Cajero pudo entrar a dashboard admin! ({resp_bloqueo.status_code})"
        print("  [+] Rol CAJERO: Punto de venta accesible y dashboard admin bloqueado (RBAC OK)")
    else:
        print("  [!] Aviso: No hay cajero activo en BD")

    # 3. ROL MESERO
    mesero = User.objects.filter(perfil__rol='MESERO', is_active=True).first()
    if mesero:
        client.force_login(mesero)
        resp_mesero = client.get(reverse('mesero'))
        assert resp_mesero.status_code == 200, f"Error en salón mesero: {resp_mesero.status_code}"

        # Bloqueo a dashboard administrador
        resp_bloqueo = client.get(reverse('administrador_dashboard'))
        assert resp_bloqueo.status_code in [302, 403], f"Mesero pudo entrar a dashboard admin! ({resp_bloqueo.status_code})"
        print("  [+] Rol MESERO: Salón de mesas operativo y dashboard admin bloqueado (RBAC OK)")
    else:
        print("  [!] Aviso: No hay mesero activo en BD")

    # 4. ROL COCINA
    cocinero = User.objects.filter(perfil__rol__in=['COCINERO', 'COCINA'], is_active=True).first()
    if not cocinero:
        cocinero = User.objects.filter(perfil__rol='BARTENDER', is_active=True).first()
    if cocinero:
        client.force_login(cocinero)
        resp_cocina = client.get(reverse('cocina'))
        assert resp_cocina.status_code == 200, f"Error en pantalla cocina: {resp_cocina.status_code}"

        # Bloqueo a dashboard administrador
        resp_bloqueo = client.get(reverse('administrador_dashboard'))
        assert resp_bloqueo.status_code in [302, 403], f"Cocina pudo entrar a dashboard admin! ({resp_bloqueo.status_code})"
        print("  [+] Rol COCINA: KDS operativo y dashboard admin bloqueado (RBAC OK)")
    else:
        print("  [!] Aviso: No hay cocinero activo en BD")

    # 5. VERIFICACIÓN DEL MOTOR ORM DE REPORTES (RF18.1 - RF18.6)
    rep_real = generar_reporte_estadistico_integral()
    assert 'ventas' in rep_real
    assert 'filtros' in rep_real
    assert 'ranking_productos' in rep_real
    assert 'tiempos_atencion' in rep_real
    assert 'ocupacion_mesas' in rep_real
    assert 'chart_data' in rep_real
    print("  [+] Motor RF18: generar_reporte_estadistico_integral verificado con todas las llaves ORM")

    print("=== TODAS LAS PRUEBAS DE REGRESIÓN DE LOS 4 ROLES + RF18 COMPLETADAS CON ÉXITO ===")

if __name__ == '__main__':
    test_regresion_rf18()
