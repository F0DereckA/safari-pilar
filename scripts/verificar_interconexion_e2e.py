import os
import sys
import django
from decimal import Decimal

sys.path.insert(0, os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Venta_safari.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from django.utils import timezone
from ventas.models import (
    PuntoVenta, Mesa, Jornada, Caja, Venta, DetalleVenta,
    Pedido, DetallePedido, Ticket, PerfilEmpleado, Producto, Categoria
)
from ventas.utils import calcular_redondeo_ley_20956

def simular_ciclo_completo_intermodular():
    print("=" * 70)
    print(">>> SIMULACIÓN DE CONEXIÓN REAL INTERMODULAR (SAFARI E2E) <<<")
    print("=" * 70)

    # 1. Asegurar Punto de Venta (Restaurante Central Safari con mesas)
    local = PuntoVenta.objects.filter(nombre__icontains='Restaurante').first()
    if not local:
        local = PuntoVenta.objects.first()
    assert local is not None, "Debe existir al menos un PuntoVenta"
    print(f"[OK] Punto de Venta activo: {local.nombre} (ID {local.id})")

    hoy = timezone.localdate()
    admin_user = User.objects.filter(is_superuser=True).first()
    if not admin_user:
        admin_user = User.objects.filter(username='rgomez').first()
    assert admin_user is not None, "Debe existir un usuario administrador"

    jornada, _ = Jornada.objects.get_or_create(
        fecha=hoy, estado='ABIERTA',
        defaults={'usuario_apertura': admin_user, 'observaciones': 'Jornada E2E Intermodular'}
    )
    print(f"[OK] Jornada operativa {jornada.id} abierta para {hoy}")

    # 2. Asignar/obtener personal operativo
    # Mesero
    mesero_perfil = PerfilEmpleado.objects.filter(rol='MESERO', activo=True, punto_venta_actual=local).first()
    if not mesero_perfil:
        mesero_perfil = PerfilEmpleado.objects.filter(rol='MESERO', activo=True).first()
        mesero_perfil.punto_venta_actual = local
        mesero_perfil.save()
    mesero_user = mesero_perfil.usuario
    print(f"[OK] Mesero en salón: {mesero_user.username} (Perfil ID {mesero_perfil.id})")

    # Cajero
    cajero_perfil = PerfilEmpleado.objects.filter(rol='CAJERO', activo=True, punto_venta_actual=local).first()
    if not cajero_perfil:
        cajero_perfil = PerfilEmpleado.objects.filter(rol='CAJERO', activo=True).first()
        cajero_perfil.punto_venta_actual = local
        cajero_perfil.save()
    cajero_user = cajero_perfil.usuario
    print(f"[OK] Cajero en caja: {cajero_user.username} (Perfil ID {cajero_perfil.id})")

    # Caja del cajero
    caja, _ = Caja.objects.get_or_create(
        jornada=jornada, cajero=cajero_user, punto_venta=local,
        defaults={'nombre': f'Caja {cajero_user.username}', 'monto_apertura': 50000, 'estado': 'ABIERTA'}
    )
    if caja.estado == 'CERRADA':
        caja.estado = 'ABIERTA'
        caja.save()
    print(f"[OK] Caja operativa {caja.id} abierta con fondo ${caja.monto_apertura:,.0f}")

    # Cocinero / Barra
    cocinero_perfil = PerfilEmpleado.objects.filter(rol='COCINA', activo=True).first()
    cocinero_user = cocinero_perfil.usuario if cocinero_perfil else admin_user

    # 3. Mesa de prueba
    mesa = Mesa.objects.filter(punto_venta=local, estado='HABILITADA').first()
    if not mesa:
        mesa = Mesa.objects.filter(punto_venta=local).first()
        mesa.liberar(forzar=True)
    assert mesa is not None, "Debe existir al menos una mesa en el local"
    print(f"[OK] Mesa seleccionada: {mesa.identificador} (Estado inicial: {mesa.estado})")

    # Productos para comanda (1 Cocina, 1 Barra)
    prod_cocina = Producto.objects.filter(
        activo=True,
        destino_operativo='COCINA'
    ).first()
    if not prod_cocina:
        prod_cocina = Producto.objects.filter(activo=True).first()

    prod_barra = Producto.objects.filter(
        activo=True,
        destino_operativo='BARRA'
    ).first()
    if not prod_barra:
        prod_barra = Producto.objects.filter(activo=True).exclude(id=prod_cocina.id).first()

    print(f"[OK] Producto Cocina: {prod_cocina.nombre} (${prod_cocina.precio_base:,.0f})")
    print(f"[OK] Producto Barra  : {prod_barra.nombre} (${prod_barra.precio_base:,.0f})")

    client_mesero = Client()
    client_mesero.force_login(mesero_user)

    # -------------------------------------------------------------
    # PASO A: Mesero ocupa la mesa
    # -------------------------------------------------------------
    print("\n--- PASO A: Mesero asigna comensales a la mesa ---")
    resp = client_mesero.post(f'/mesero/?local_id={local.id}', {
        'accion': 'ocupar_mesa',
        'mesa_id': str(mesa.id)
    }, follow=True)
    mesa.refresh_from_db()
    assert mesa.estado == 'OCUPADA', f"La mesa debió quedar OCUPADA pero está {mesa.estado}"
    print(f"[PASS] Mesa {mesa.identificador} marcada correctamente como {mesa.estado}")

    # -------------------------------------------------------------
    # PASO B: Mesero emite comanda con comida y bebida
    # -------------------------------------------------------------
    print("\n--- PASO B: Mesero envía comanda a Cocina y Barra ---")
    import json
    items_comanda = [
        {
            'id': prod_cocina.id,
            'nombre': prod_cocina.nombre,
            'cantidad': 2,
            'precio': int(prod_cocina.precio_base),
            'destino': 'COCINA',
            'nota': 'Sin mayonesa'
        },
        {
            'id': prod_barra.id,
            'nombre': prod_barra.nombre,
            'cantidad': 2,
            'precio': int(prod_barra.precio_base),
            'destino': 'BARRA',
            'nota': 'Bien heladas'
        }
    ]
    resp = client_mesero.post(f'/mesero/?local_id={local.id}', {
        'accion': 'enviar_comanda',
        'mesa_id': str(mesa.id),
        'items_json': json.dumps(items_comanda)
    }, follow=True)

    # Verificar que se creó la Venta abierta y los pedidos
    venta_abierta = Venta.objects.filter(mesa=mesa, estado='ABIERTA').first()
    assert venta_abierta is not None, "Debe existir una Venta ABIERTA para la mesa"
    subtotal_esperado = (prod_cocina.precio_base * 2) + (prod_barra.precio_base * 2)
    assert venta_abierta.total == subtotal_esperado, f"Total venta {venta_abierta.total} != {subtotal_esperado}"
    print(f"[PASS] Venta abierta creada: ID #{venta_abierta.id} por ${venta_abierta.total:,.0f}")

    pedidos_mesa = Pedido.objects.filter(venta=venta_abierta)
    print(f"[PASS] Pedidos generados para la orden: {pedidos_mesa.count()} comanda(s)")
    for ped in pedidos_mesa:
        print(f"       -> Comanda #{ped.id} | Destino: {repr(ped.observaciones)} | Estado: {ped.estado}")

    # -------------------------------------------------------------
    # PASO C: KDS Cocina y KDS Barra actualizan estado
    # -------------------------------------------------------------
    print("\n--- PASO C: Transición de estados en KDS Cocina y Barra ---")
    client_cocina = Client()
    client_cocina.force_login(cocinero_user)

    for ped in pedidos_mesa:
        # PENDIENTE -> EN_PREPARACION
        resp = client_cocina.post('/cocina/cambiar-estado/', {
            'pedido_id': str(ped.id),
            'nuevo_estado': 'EN_PREPARACION'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        ped.refresh_from_db()
        assert ped.estado == 'EN_PREPARACION', f"Pedido #{ped.id} debió pasar a EN_PREPARACION"
        print(f"[PASS] Comanda #{ped.id}  -> {ped.estado}")

        # EN_PREPARACION -> LISTO
        resp = client_cocina.post('/cocina/cambiar-estado/', {
            'pedido_id': str(ped.id),
            'nuevo_estado': 'LISTO'
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        ped.refresh_from_db()
        assert ped.estado == 'LISTO', f"Pedido #{ped.id} debió pasar a LISTO"
        print(f"[PASS] Comanda #{ped.id}  -> {ped.estado}")

    # -------------------------------------------------------------
    # PASO D: Monitor en tiempo real (Polling Delta API)
    # -------------------------------------------------------------
    print("\n--- PASO D: Verificación de API de Sincronización en Tiempo Real ---")
    client_cajero = Client()
    client_cajero.force_login(cajero_user)
    resp = client_cajero.get(f'/api/sincronizacion/estado/?local_id={local.id}')
    assert resp.status_code == 200, f"Error en API de sincronización: {resp.status_code}"
    delta = resp.json()
    print(f"[PASS] API /api/sincronizacion/estado/ responde OK 200.")
    print(f"       Mesas ocupadas reportadas: {delta.get('mesas_ocupadas_count', 0)}")
    print(f"       Pedidos listos en salón  : {delta.get('pedidos_listos_count', 0)}")

    # -------------------------------------------------------------
    # PASO E: Cajero cobra la cuenta de la mesa en el POS
    # -------------------------------------------------------------
    print("\n--- PASO E: Cajero liquida la mesa en POS con Redondeo Ley N° 20.956 ---")
    total_venta = venta_abierta.total
    redondeado_ley, ajuste = calcular_redondeo_ley_20956(total_venta)
    print(f"       Total consumido : ${total_venta:,.0f}")
    print(f"       Redondeo Ley    : ${redondeado_ley:,.0f} (Ajuste: ${ajuste:+,.0f})")

    resp = client_cajero.post('/vendedor/', {
        'accion': 'cobrar_cuenta_mesa',
        'mesa_id': str(mesa.id),
        'metodo_pago': 'EFECTIVO',
        'monto_pago': str(total_venta),
        'incluir_propina': '0'
    }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    
    assert resp.status_code == 200, f"Error cobrando mesa: {resp.content.decode()}"
    res_json = resp.json()
    assert res_json.get('ok') is True, f"Fallo al cobrar mesa: {res_json}"
    print(f"[PASS] Cobro exitoso reportado por el backend: {res_json.get('mensaje')}")

    # Verificar que la venta pasó a PAGADA
    venta_abierta.refresh_from_db()
    assert venta_abierta.estado == 'PAGADA', f"Venta debió quedar PAGADA pero está {venta_abierta.estado}"
    print(f"[PASS] Venta #{venta_abierta.id} en estado PAGADA.")

    # Verificar que la mesa fue liberada automáticamente
    mesa.refresh_from_db()
    assert mesa.estado == 'HABILITADA', f"Mesa debió quedar HABILITADA pero está {mesa.estado}"
    print(f"[PASS] Mesa {mesa.identificador} liberada automáticamente: {mesa.estado}")

    # Verificar generación de Ticket
    ticket = Ticket.objects.filter(venta=venta_abierta).first()
    assert ticket is not None, "Debe existir un Ticket asociado a la venta"
    print(f"[PASS] Ticket emitido: Código {ticket.codigo} | Total Venta: ${venta_abierta.total:,.0f} | Redondeo: ${venta_abierta.redondeo_ley_20956:,.0f}")

    print("\n" + "=" * 70)
    print(">>> 100% ÉXITO: EL FLUJO COMPLETO INTERMODULAR OPERA A LA PERFECCIÓN <<<")
    print("=" * 70)

if __name__ == '__main__':
    simular_ciclo_completo_intermodular()
