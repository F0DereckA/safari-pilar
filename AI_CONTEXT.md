# AI_CONTEXT

## 1. proyecto
- nombre: Venta_safari
- tipo de proyecto: Web (Django)
- tecnologías principales: Python 3.14.6, Django 6.1, Bootstrap 5.3, Bootstrap Icons 1.11, JavaScript (Vanilla), CSS3 modular, SQLite

## 2. objetivo actual
- tarea actual: **PLAN MAESTRO DE IMPLEMENTACIÓN RF07–RF18 — cierre integral de requerimientos oficiales, robustez operacional y pruebas de aceptación**.
- punto de partida confirmado:
  - RF05 Reasignación de Mesas: **COMPLETADO Y TESTEADO (93/93 suite vigente)**.
  - RF07 Gestión de Precios: **COMPLETADO Y TESTEADO (107/107 suite vigente en verde al cerrar RF07)**.
  - RF08 Generación de Tickets: **COMPLETADO Y TESTEADO (116/116 suite vigente en verde al cerrar RF08)**.
  - RF09 Gestión de Impresión: **COMPLETADO Y TESTEADO (127/127 suite vigente en verde al cerrar RF09 con KDS Barra)**.
  - RF01–RF09: implementaciones estables y blindadas; no modificar sin auditoría previa.
- objetivo: completar de forma incremental, verificable y sin regresiones los RF07–RF18 definidos por el docente.
- método obligatorio para cada RF:
  1. auditar estado real;
  2. identificar qué ya existe y qué falta;
  3. implementar el cambio mínimo necesario;
  4. blindar errores y concurrencia;
  5. ejecutar pruebas unitarias/integración;
  6. ejecutar `python manage.py check`;
  7. ejecutar suite completa;
  8. hacer regresión manual de los 4 roles;
  9. documentar resultado exacto;
  10. detener antes de pasar al siguiente RF.
- módulos extra de huéspedes/cabañas/desayuno/ofertas:
  - mantener funcionales y congelados;
  - no ampliarlos;
  - solo reutilizar lógica si encaja de forma directa con un RF oficial.
- prohibido durante este plan:
  - desarrollar RF19–RF24;
  - agregar funcionalidades no solicitadas;
  - presentar mocks como datos reales;
  - cambiar el modelo masivamente sin auditoría previa;
  - continuar al RF siguiente si la suite actual falla.
---



### PLAN MAESTRO RF07–RF18 — ORDEN COMPLETO DE INICIO A FIN

> [!IMPORTANT]
> Este bloque reemplaza cualquier “siguiente paso” parcial anterior. Antigravity debe trabajar RF por RF, en el orden indicado. No ejecutar todo de una sola vez. Cada RF se considera cerrado solo cuando cumple su criterio de aceptación y la suite completa continúa en verde.

---

## ETAPA 0 — PREPARACIÓN Y LÍNEA BASE ANTES DE RF07

### Objetivo
Congelar una línea base estable después de RF05 para detectar cualquier regresión futura.

### Tareas
1. Ejecutar:
   - `python manage.py check`
   - `python manage.py test ventas`
   - `python manage.py showmigrations`
2. Registrar:
   - número exacto de tests vigentes;
   - migraciones aplicadas;
   - motor de BD realmente activo;
   - fecha/hora de la línea base.
3. Verificar manualmente:
   - ADMINISTRADOR inicia sesión y abre panel.
   - CAJERO inicia sesión, ve jornada/caja.
   - MESERO ve mesas y cuenta abierta.
   - COCINERO ve KDS.
4. Confirmar que RF05 sigue funcional:
   - reasignación válida;
   - destino ocupado rechazado;
   - no duplica tickets.
5. No modificar aún lógica funcional.

### Criterio de aceptación
- `check` limpio.
- suite completa OK.
- cuatro roles accesibles.
- RF05 sin regresiones.

---

# RF07 — GESTIÓN DE PRECIOS DURANTE LA VENTA — [ESTADO: COMPLETADO Y CERRADO (107/107 OK)]

### Resumen de Cierre y Verificación Oficial (RF07)
- **Fecha de Cierre:** 2026-10-31 / 2026-11-01
- **Migraciones Aplicadas:** `0013_detalleventa_autorizado_por_and_more.py` y `0014_precioespecial_codigo_convenio.py`.
- **Modelos Actualizados:**
  * `DetalleVenta`: campos de trazabilidad `precio_original`, `es_precio_especial`, `motivo_precio_especial`, `autorizado_por`.
  * `RegistroPrecioEspecial`: modelo inmutable de auditoría con `venta`, `detalle_venta`, `producto`, `precio_original`, `precio_aplicado`, `descuento_unitario`, `cantidad`, `usuario`, `motivo`, `convenio_origen`, `fecha_hora`.
  * `PrecioEspecial`: campo `codigo_convenio` (QR/alfanumérico) y método `es_vigente(fecha=None)`.
- **Lógica Financiera y Blindaje (`ventas/utils.py`):**
  * `validar_y_calcular_precio_linea()`: precio base siempre tomado de `Producto.precio_base` en BD; rechazo de precios <= 0 y no numéricos; control estricto de roles autorizados (`ADMINISTRADOR`, `CAJERO`); validación de vigencia de convenios; inmutabilidad garantizada de `Producto.precio_base`.
  * `registrar_precio_especial_auditoria()`: persistencia inmutable en tabla de auditoría y DetalleVenta.
- **Vistas Integradas (`ventas/views.py`):**
  * `mesero` (`enviar_comanda`): validación servidor, protección contra alteración de precios desde cliente (el servidor ignora precios manipulados por mesero/navegador y aplica el oficial de BD).
  * `crear_ticket`: soporte POST POS venta rápida con validación atómica, cálculo de Ley 20.956 de redondeo y auditoría RF07.
  * `api_verificar_convenio_qr`: soporte de QR/códigos para convenios institucionales comerciales (RF07.5) preservando compatibilidad con huéspedes.
  * `administrador_historial`: panel consolidado de auditoría que incluye eventos tipo `PRECIOS` con ahorros y motivos.
- **Resultados de Pruebas Automatizadas:**
  * Tests específicos RF07 (`SafariRF07GestionPreciosTests`): 14/14 tests OK.
  * Suite completa (`python manage.py test ventas`): **107/107 tests pasados exitosamente en 207.6s (0 fallos, 0 errores)**.
  * `python manage.py check`: 0 issues.
- **Verificación de 4 Roles:**
  * ADMINISTRADOR (`rgomez`): 200 OK.
  * CAJERO (`cvalenzuela`): 200 OK.
  * MESERO (`dsilva`): 200 OK.
  * COCINERO (`eparedes`): 200 OK.
  * RF05 (Reasignación de Mesas): intacto y verificado.

## Objetivo oficial
Permitir modificar, cuando corresponda, el precio de un producto al generar una venta para valores especiales asociados a convenios u otras condiciones comerciales autorizadas.

## Auditoría previa obligatoria
1. Revisar `Producto`, `PrecioEspecial`, `DetalleVenta`, `Venta`.
2. Revisar cómo se obtiene actualmente el precio en:
   - Mesero.
   - Cajero.
   - venta rápida.
3. Verificar si el precio actual se toma desde cliente/JavaScript o desde BD.
4. Revisar si ya existe autorización por rol o supervisor.
5. Revisar si la lógica antigua de convenios/QR puede reutilizarse sin depender de huéspedes/cabañas/desayuno.

## Tareas funcionales
### RF07.1 Precio base
- El precio base siempre se consulta desde `Producto` en BD.
- Nunca confiar en precio recibido desde frontend.

### RF07.2 Precio especial por operación
- Aplicar precio especial solo al detalle de venta actual.
- NO modificar permanentemente `Producto.precio`.

### RF07.3 Autorización
- Definir según estructura existente quién puede:
  - aplicar precio especial;
  - autorizarlo;
  - modificarlo.
- Si Cajero puede hacerlo directamente por requerimiento, registrar quién lo aplicó.
- Si existe autorización de supervisor ya implementada, reutilizarla solo si no contradice RF07.

### RF07.4 Trazabilidad
Registrar como mínimo:
- producto;
- precio original;
- precio aplicado;
- usuario;
- motivo/convenio;
- fecha/hora;
- venta relacionada.

### RF07.5 Convenios
- Generalizar a `Convenio / Beneficio Autorizado`.
- QR puede ser una forma opcional de identificar convenio.
- No depender de cabaña, huésped ni desayuno.

## Problemas que debe soportar
1. precio especial = 0;
2. precio negativo;
3. valor no numérico;
4. usuario sin permiso;
5. producto inactivo;
6. producto eliminado;
7. convenio inexistente;
8. convenio inactivo/vencido;
9. beneficio aplicado dos veces;
10. navegador manipula precio;
11. precio base cambió mientras la pantalla estaba abierta;
12. venta anulada después del precio especial;
13. doble clic;
14. dos usuarios modifican simultáneamente la misma venta;
15. error de BD a mitad del cobro.

## Pruebas mínimas
- precio normal;
- precio especial válido;
- rechazo de precio 0/negativo;
- rechazo de no autorizado;
- revalidación servidor;
- trazabilidad;
- convenio válido/inválido si se usa;
- rollback ante error;
- doble envío no duplica.

## Criterio de aceptación RF07
- precio base intacto;
- detalle de venta conserva precio aplicado;
- trazabilidad completa;
- no se puede manipular precio desde cliente;
- suite completa OK.

## Detener
Actualizar `AI_CONTEXT.md` y no iniciar RF08 hasta revisión.

---

# RF08 — GENERACIÓN DE TICKETS — [ESTADO: COMPLETADO Y CERRADO (116/116 OK)]

### Resumen de Cierre y Verificación Oficial (RF08)
- **Fecha de Cierre:** 2026-10-31 / 2026-11-01
- **Migración Aplicada:** 0015_categoria_destino_defecto_producto_destino_operativo_and_more.py
- **Modelos Actualizados:**
  * Categoria: destino_defecto (COCINA/BARRA).
  * Producto: destino_operativo (COCINA/BARRA/COMPROBANTE) con método get_destino_operativo().
  * Ticket: venta (FK), es_reimpresion, numero_reimpresiones, ultima_reimpresion_por, fecha_hora_reimpresion.
- **Motor de Emisión de Tickets (ventas/utils.py):**
  * generar_contenido_ticket_cocina(), generar_contenido_ticket_barra(), generar_contenido_comprobante_venta().
  * emitir_tickets_comanda(): clasificación estricta por destino de BD, política de cero tickets vacíos, soporte de rondas incrementales (solo emite tickets para los ítems de la comanda/ronda actual).
  * emitir_comprobante_venta(): detalle financiero con total pagado, método de pago y formato fiscal/térmico.
  * reimprimir_ticket(): trazabilidad inmutable sin duplicación de ventas ni mutación de caja.
- **Vistas y Endpoints (ventas/views.py y urls.py):**
  * enviar_comanda: emisión desacoplada por destino.
  * cerrar_cuenta_mesa y crear_ticket: generación de comprobante y tickets operativos.
  * reimprimir_ticket_view: endpoint seguro para reimpresión con trazabilidad de auditoría.
- **Resultados de Pruebas Automatizadas:**
  * Tests específicos RF08 (SafariRF08GeneracionTicketsTests): 9/9 tests OK.
  * Suite completa (python manage.py test ventas): 116/116 tests pasados exitosamente (0 fallos, 0 errores).
  * python manage.py check: 0 issues.

## Objetivo oficial
Generar tickets según operación:
- Cocina: elaboración propia.
- Barra: productos terminados/bebidas/snacks/tickets de juegos.
- Comprobante de venta.

## Auditoría previa
1. Revisar modelos `Ticket`, `Pedido`, `DetallePedido`, `DetalleVenta`.
2. Revisar destinos actuales `COCINA`, `BARRA`.
3. Verificar cómo se genera comprobante de venta.
4. Revisar reglas de productos por categoría/tipo/destino.
5. Verificar si venta rápida y mesa usan el mismo origen de datos.

## Tareas
### RF08.1 Clasificación por destino
- definir desde BD el destino operativo;
- evitar reglas duplicadas en JS.

### RF08.2 Ticket Cocina
Debe incluir, si existe:
- número/código;
- mesa o venta rápida;
- hora;
- productos de elaboración;
- cantidad;
- observaciones RF12;
- ronda/pedido.

### RF08.3 Ticket Barra
- productos terminados;
- bebidas;
- snacks;
- tickets/juegos cuando corresponda.

### RF08.4 Comprobante de venta
- total;
- detalles;
- precios aplicados;
- modalidad;
- usuario/caja;
- fecha/hora.

### RF08.5 Incrementalidad
- segunda ronda genera solo tickets nuevos;
- nunca reimprimir productos anteriores salvo reimpresión explícita.

### RF08.6 Reimpresión
- reimpresión debe ser trazable;
- no crear una venta nueva;
- no duplicar detalles.

## Problemas
1. pedido sin productos;
2. producto sin destino;
3. producto mal clasificado;
4. ticket vacío;
5. doble generación;
6. segunda ronda reimprime ronda anterior;
7. venta rápida genera ticket de mesa incorrecto;
8. error entre persistencia de venta y ticket;
9. reimpresión crea duplicado lógico;
10. ticket de cocina incluye producto de barra;
11. ticket de barra incluye elaboración;
12. caracteres especiales/observaciones largas.

## Pruebas
- Cocina;
- Barra;
- comprobante;
- pedido mixto;
- segunda ronda;
- reimpresión;
- pedido vacío;
- clasificación correcta;
- trazabilidad.

## Criterio RF08
- todos los destinos correctos;
- cero tickets vacíos;
- no duplicación;
- suite completa OK.

---

# RF09 — GESTIÓN DE IMPRESIÓN — [ESTADO: COMPLETADO Y CERRADO (125/125 OK)]

### Resumen de Cierre y Verificación Oficial (RF09)
- **Fecha de Cierre:** 2026-11-01
- **Migración Aplicada:** `0016_ticket_error_impresion_ticket_estado_impresion_and_more.py`
- **Modelos Creados y Actualizados (`ventas/models.py`):**
  * `PuntoImpresion`: entidad de configuración física/digital asociada a `PuntoVenta` con `tipo_destino` (`COCINA`, `BARRA`, `COMPROBANTE`), `tipo_conexion` (`DIGITAL`, `RED`, `USB`), `direccion_ip`, `puerto`, `ancho_papel_mm` (80mm / 58mm), `estado_operativo` (`ONLINE`, `OFFLINE`, `SIN_PAPEL`, `ERROR`), `simular_fallo`. Restricción única por local y destino: `unique_together = ('punto_venta', 'tipo_destino')`.
  * `Ticket`: campos de gestión de despacho `punto_venta`, `punto_impresion`, `estado_impresion` (`PENDIENTE`, `IMPRESO`, `FALLO`), `error_impresion`, `intentos_impresion` y método de resolución de local emisor `get_punto_venta()`.
  * `RegistroImpresion`: auditoría inmutable de cada despacho o reintento de impresión (`ticket`, `punto_impresion`, `exitoso`, `modo`, `mensaje_error`, `es_reintento`, `usuario`, `fecha_hora`).
- **Capa y Servicio Lógico de Impresión (`ventas/utils.py`):**
  * `obtener_o_crear_punto_impresion()`: resolución inteligente de impresoras asignadas por local y destino.
  * `enviar_a_impresora()`: servicio de despacho desacoplado. Soporta modo `DIGITAL` con render térmico, modo `RED` mediante socket ESC/POS con timeout estricto de 1.0s, y modo resiliente ante fallos de hardware o sin papel.
  * **Regla Crítica de Oro (RF09.4):** Si la impresora falla, está desconectada, o se queda sin papel, **la venta y el pedido persisten 100% intactos en la BD**; el ticket queda en estado `FALLO` con auditoría detallada y disponible para reintento.
  * `reintentar_despacho_impresion()`: reintento idempotente que vuelve a despachar a la impresora una vez restablecida, sin duplicar ventas ni corromper saldos contables.
  * `reimprimir_ticket()`: ahora re-despacha automáticamente la copia trazable a su punto de impresión registrado.
- **Vistas, Endpoints y Plantillas:**
  * Endpoint de previsualización e impresión digital térmica: `/tickets/<int:ticket_id>/imprimir/` ([`ticket_impresion_digital.html`](file:///c:/Users/pc/Desktop/safari%20Pilar/ventas/templates/ventas/ticket_impresion_digital.html)) con formato monospace 80mm/58mm, alerta de estado, botón `window.print()` y reintento.
  * Endpoint de reintento de despacho: `/tickets/<int:ticket_id>/reintentar/` con soporte HTTP y AJAX.
  * **Pantalla Táctil KDS Barra & Cafetería (`/barra/` y [`barra.html`](file:///c:/Users/pc/Desktop/safari%20Pilar/ventas/templates/ventas/barra.html)):** Módulo operativo en pantalla equivalente al KDS de Cocina en reemplazo de tickets físicos de papel. Cumple estrictamente las mismas condiciones operacionales: sin temporizador de 15 minutos, auto-actualización en vivo cada 1 segundo con Scroll-Lock (sin saltos arriba), cero botones manuales de refresco, y aislamiento exclusivo de ítems de barra (bebidas, cafetería, jugos, snacks).
  * Integración en `administrador_historial`: registro de eventos de fallos y reintentos de impresión (`tipo: IMPRESION`).
  * Admin Django: `PuntoImpresionAdmin` y `RegistroImpresionAdmin` registrados en `ventas/admin.py`.
  * Poblamiento Demo: comando `poblar_safari.py` inicializa automáticamente los 3 puntos de impresión oficiales para cada uno de los 3 locales.
- **Resultados de Pruebas Automatizadas:**
  * Tests específicos RF09 (`SafariRF09GestionImpresionTests`): 11/11 tests OK.
  * Suite completa (`python manage.py test ventas`): **127/127 tests pasados exitosamente (0 fallos, 0 errores)**.
  * `python manage.py check`: 0 issues.
- **Regresión Manual de 4 Roles:**
  * Administrador (`rgomez`): 200 OK.
  * Cajero (`cvalenzuela`): 200 OK.
  * Mesero (`dsilva`): 200 OK.
  * Cocinero (`eparedes`): 200 OK.
  * RF05 (Reasignación de Mesas): intacto y verificado.

## Objetivo oficial
Considerar tres puntos de impresión físicos en restaurante; provisionalmente digital.

## Auditoría
1. Identificar las tres salidas lógicas actuales.
2. Revisar si existe configuración de impresora o solo render digital.
3. Confirmar que ticket y persistencia están desacoplados.

## Tareas
### RF09.1 Capa de impresión
- crear/usar servicio lógico de impresión;
- separar:
  - generación del ticket;
  - persistencia;
  - envío a impresora.

### RF09.2 Tres puntos
Definir como mínimo:
- Cocina.
- Barra.
- Comprobante/venta.

### RF09.3 Modo digital provisional
- mantener previsualización/impresión digital funcional;
- dejar preparado punto de integración física sin exigir hardware.

### RF09.4 Reintento
- si impresión falla, venta no debe perderse;
- permitir reimpresión.

## Problemas
1. impresora desconectada;
2. impresora sin papel;
3. timeout;
4. impresora equivocada;
5. doble clic;
6. venta registrada pero impresión falló;
7. reimpresión;
8. impresión parcial Cocina sí/Barra no;
9. reinicio del navegador;
10. impresora configurada para otro local.

## Pruebas
- enrutamiento;
- fallo simulado de impresión;
- reimpresión;
- venta persiste aunque falle impresión;
- local correcto.

## Criterio RF09
- lógica de 3 destinos documentada;
- fallo de impresión no destruye operación;
- reimpresión segura;
- suite OK.

---

# RF10 — CONSUMO INTERNO DEL PERSONAL / FIADO

## Auditoría
Revisar:
- `ConsumoInterno`;
- `DetalleConsumoInterno`;
- trabajadores;
- Producto;
- PuntoVenta;
- historial existente.

## Tareas
### RF10.1 Selección de trabajador
- solo trabajadores válidos;
- mostrar estado activo.

### RF10.2 Registro
- productos;
- cantidades;
- precios oficiales;
- local;
- fecha/hora;
- usuario que registra.

### RF10.3 Acumulado
- total por trabajador;
- historial detallado;
- filtros por fecha/local.

### RF10.4 Separación contable
- no mezclar con venta de cliente;
- no sumar a caja como venta normal salvo que política futura lo indique.

### RF10.5 Integridad
- operación atómica encabezado + detalles.

## Problemas
- trabajador inexistente/inactivo;
- producto inválido;
- precio manipulado;
- cantidad <=0;
- doble envío;
- otro local;
- eliminación de trabajador con historial;
- rollback;
- producto desactivado durante operación.

## Pruebas
- consumo válido;
- acumulado;
- rechazo trabajador/producto;
- doble envío;
- rollback;
- historial.

## Criterio
- fiado correcto;
- acumulado real;
- historial íntegro;
- suite OK.

---

# RF11 — ASIGNACIÓN DE MESA O VENTA RÁPIDA

## Objetivo oficial
Cuando hay elaboración propia, indicar si va a mesa o retiro rápido.

## Auditoría
1. Revisar modalidad actual de `Venta`.
2. Revisar valores existentes para mesa/venta rápida.
3. Revisar cómo se comporta Cocina/Barra.

## Tareas
### RF11.1 Modalidad
- `MESA` requiere mesa válida.
- `VENTA_RAPIDA` no requiere mesa.

### RF11.2 Flujo Mesa
- cuenta abierta;
- múltiples rondas;
- cierre posterior.

### RF11.3 Flujo Venta rápida
- una sola operación;
- retiro en barra;
- no ocupar mesa.

### RF11.4 Validación
- impedir modalidad inconsistente.

## Problemas
- mesa no seleccionada;
- mesa ocupada por otro;
- venta rápida con mesa;
- cambio de modalidad a mitad;
- doble envío;
- producto elaborado en venta rápida;
- error tras generar pedido.

## Pruebas
- mesa;
- rápida;
- mesa requerida;
- no ocupar mesa en rápida;
- tickets correctos.

## Criterio
- ambas modalidades separadas y consistentes;
- suite OK.

---

# RF12 — COMENTARIOS ASOCIADOS A PRODUCTOS

## Auditoría
Revisar `DetallePedido.observaciones` y UI actual.

## Tareas
- comentario por producto;
- texto libre;
- conservar por ronda;
- mostrar en ticket Cocina/Barra cuando aplique;
- escapar HTML;
- límite razonable de longitud.

## Problemas
- XSS;
- texto vacío;
- texto excesivo;
- caracteres especiales;
- comentario del producto A aparece en B;
- segunda ronda hereda comentario viejo;
- reimpresión pierde comentario.

## Pruebas
- persistencia;
- separación por producto;
- escaping;
- segunda ronda;
- ticket.

## Criterio
- observaciones exactas y seguras;
- suite OK.

---

# RF13 — REGISTRO DE ENTREGA DE PRODUCTOS

## Auditoría
Revisar `Entrega`, `Pedido`, `Ticket` y estados KDS.

## Tareas
### RF13.1 Flujo
PENDIENTE -> EN PREPARACIÓN -> LISTO -> ENTREGADO.

### RF13.2 Registro
- fecha/hora;
- usuario que entrega;
- pedido/ticket;
- local;
- mesa/venta rápida.

### RF13.3 Granularidad
- determinar según modelo real si entrega es por pedido, ticket o ítem;
- no inventar estructura sin auditoría.

### RF13.4 Doble entrega
- impedir duplicados.

## Problemas
- entregar antes de listo;
- entregar dos veces;
- pedido cancelado;
- Cocina y Barra terminan distinto;
- ronda equivocada;
- concurrencia Cocina/Mesero;
- error de BD.

## Pruebas
- flujo válido;
- transición inválida;
- doble entrega;
- ronda correcta;
- registro usuario/hora.

## Criterio
- entrega real y trazable;
- suite OK.

---

# RF14 — GESTIÓN DE PUNTOS DE VENTA

## Auditoría
Ya existe CRUD; verificar cumplimiento oficial.

## Tareas
- crear;
- modificar;
- activar/desactivar;
- proteger históricos;
- asignar trabajadores;
- asociar mesas/productos/menús;
- impedir duplicados de nombre si aplica.

## Problemas
- eliminar con historial;
- desactivar con jornada/venta abierta;
- reasignación de trabajadores;
- local inexistente;
- datos duplicados;
- acceso no Admin.

## Pruebas
- CRUD;
- soft-delete;
- histórico;
- permisos.

## Criterio
- RF14 confirmado, no necesariamente reescrito.

---

# RF15 — POSICIONAMIENTO DE PRODUCTOS Y MENÚS

## Objetivo
Definir qué productos ofrece cada Punto de Venta.

## Auditoría
Revisar relaciones actuales Producto/PuntoVenta/Menu.

## Tareas
- menú por local;
- productos habilitados por local;
- evitar que Cajero/Mesero venda producto no disponible en ese local;
- fuente de verdad BD;
- eliminar mocks/hardcodes progresivamente.

## Problemas
- producto en local incorrecto;
- producto desactivado;
- menú vacío;
- producto retirado del menú con ventas históricas;
- terminal antigua conserva producto ya deshabilitado.

## Pruebas
- producto disponible;
- producto no disponible rechazado;
- menú por local;
- actualización dinámica.

## Criterio
- terminales consultan catálogo real o backend valida siempre disponibilidad;
- suite OK.

---

# RF16 — CONTROL DE TIEMPOS DE ATENCIÓN

## Dependencia
RF13 debe estar cerrado.

## Tareas
Calcular:
- creación pedido;
- inicio preparación;
- listo;
- entregado;
- tiempo preparación;
- espera total.

## Problemas
- timestamps faltantes;
- orden temporal inválido;
- pedido no entregado;
- cambio de día;
- zona horaria;
- ronda separada.

## Pruebas
- tiempos normales;
- no negativos;
- incompletos no inventados;
- Chile timezone.

## Criterio
- tiempos reales disponibles para reportes.

---

# RF17 — GESTIÓN DE OCUPACIÓN DE MESAS

## Dependencias
RF05 y Mesa/Cuenta Abierta.

## Tareas
- inicio ocupación;
- duración;
- liberación;
- estado actual;
- reasignación;
- nueva ronda no reinicia tiempo.

## Problemas
- doble ocupación;
- liberar con cuenta abierta;
- cierre falla;
- mesa desactivada ocupada;
- jornada cambia;
- navegador se reinicia.

## Pruebas
- ocupación;
- múltiples rondas;
- reasignación;
- cierre;
- concurrencia.

## Criterio
- estado reconstruible 100% desde BD;
- suite OK.

---

# RF18 — REPORTES Y ESTADÍSTICAS

## Dependencias
RF06, RF13, RF16, RF17.

## Mínimos oficiales
- ventas realizadas;
- productos más vendidos;
- tiempos de espera y entrega.

## Tareas
### RF18.1 Eliminar mocks
- identificar KPIs hardcodeados;
- sustituir por ORM real.

### RF18.2 Filtros
- fecha inicio/fin;
- PuntoVenta;
- usuario cuando corresponda.

### RF18.3 Ventas
- totales;
- cantidad;
- modalidad;
- precios especiales.

### RF18.4 Productos
- ranking por cantidad;
- considerar históricos.

### RF18.5 Tiempos
- promedio;
- mínimo/máximo si corresponde;
- solo entregas válidas.

### RF18.6 Ocupación
- solo si RF17 produce datos reales.

## Problemas
- día sin ventas;
- rango inválido;
- local sin datos;
- producto desactivado;
- venta anulada;
- precio especial;
- pedido sin entrega;
- N+1;
- volumen alto.

## Pruebas
- totales;
- ranking;
- tiempos;
- filtros;
- vacío;
- rendimiento básico.

## Criterio
- 100% datos reales;
- ningún KPI demo presentado como real;
- suite OK.

---

# ETAPA FINAL — AUDITORÍA INTEGRAL RF01–RF18

## Objetivo
Confirmar que todos los requerimientos oficiales están cubiertos sin contradicciones.

## Checklist funcional
- RF01 Usuarios.
- RF02 Jornada.
- RF03 Caja individual.
- RF04 Mesas.
- RF05 Reasignación.
- RF06 Ventas.
- RF07 Precios especiales.
- RF08 Tickets.
- RF09 Impresión.
- RF10 Consumo interno.
- RF11 Mesa / venta rápida.
- RF12 Comentarios.
- RF13 Entrega.
- RF14 Puntos de Venta.
- RF15 Productos/Menús por local.
- RF16 Tiempos.
- RF17 Ocupación.
- RF18 Reportes.

## Auditoría técnica final
1. `manage.py check`.
2. suite completa.
3. migraciones.
4. revisión de permisos.
5. revisión de concurrencia.
6. revisión de doble envío.
7. revisión de soft-delete/históricos.
8. revisión de mocks restantes.
9. revisión de secretos/configuración.
10. revisión de errores 400/403/404/500.
11. revisión manual en pantalla táctil y móvil Mesero.
12. revisión de impresión digital provisional.

## Auditoría documental final
- actualizar modelo lógico 1:1 con `models.py`;
- actualizar modelo físico;
- incluir Azure DevOps;
- redacción impersonal;
- plantilla de pares;
- pruebas unitarias/integración/rendimiento;
- evidencias por RF;
- no mencionar RF19–RF24.

## Regla final
No declarar un RF como “COMPLETADO” únicamente porque exista una vista. Debe existir:
- persistencia real;
- validación;
- seguridad;
- manejo de fallos;
- prueba automatizada o evidencia reproducible;
- regresión completa.

---

### PLAN FUNCIONAL PRIORITARIO RF01–RF18 — ROBUSTEZ OPERACIONAL (HISTÓRICO / REFERENCIA)

> [!IMPORTANT]
> El objetivo de esta fase no es agregar funciones nuevas fuera del alcance. Es cerrar correctamente los requerimientos oficiales pendientes y preparar el sistema para situaciones reales de uso en Parque Safari.

#### PRINCIPIOS GENERALES PARA TODA ESTA FASE
1. El servidor y la base de datos son la fuente de verdad.
2. No confiar en precio, rol, local, mesa, usuario, total o estado enviados desde JavaScript cuando exista un dato oficial en BD.
3. Toda operación que modifique varias entidades relacionadas debe evaluarse para ejecutarse dentro de `transaction.atomic()`.
4. Cuando exista riesgo de dos usuarios actuando sobre el mismo registro al mismo tiempo, evaluar bloqueo transaccional (`select_for_update`) o validación equivalente.
5. Los botones críticos deben ser resistentes a doble clic / doble envío.
6. No eliminar físicamente información histórica si ya participa en ventas, consumos, pedidos, entregas o trazabilidad.
7. Los errores deben responder de forma controlada, sin stack trace ni corrupción parcial de datos.
8. Cada cambio debe terminar con:
   - `python manage.py check`;
   - `python manage.py test ventas`;
   - pruebas específicas del nuevo escenario;
   - regresión de ADMINISTRADOR, CAJERO, MESERO y COCINERO.
9. No reintroducir ni desarrollar Requerimientos Futuros 19–24.

---

#### RF05 — REASIGNACIÓN DE MESAS [COMPLETADO AL 100%]

**Objetivo funcional**
Permitir trasladar una atención/venta/pedido activo desde una mesa origen hacia otra mesa destino cuando el cliente solicite cambio, manteniendo intactos total, pedidos anteriores, rondas, observaciones, tickets y trazabilidad.

**Comportamiento esperado**
- La atención abierta debe seguir siendo la misma; no crear una nueva venta solo por cambiar de mesa.
- La mesa origen debe quedar disponible únicamente si ya no conserva otra atención activa.
- La mesa destino debe quedar ocupada por la atención reasignada.
- Los tickets de Cocina/Barra ya generados NO deben volver a imprimirse por el cambio de mesa.
- Las nuevas comandas posteriores al traslado deben mostrar la nueva mesa.
- El historial debe permitir saber que existió una reasignación de mesa.

**Escenarios problemáticos obligatorios**
1. Mesa origen no existe.
2. Mesa destino no existe.
3. Origen y destino son la misma mesa.
4. La mesa origen no tiene una cuenta/venta abierta.
5. La mesa destino ya tiene una cuenta abierta de otros clientes.
6. La mesa destino está deshabilitada/inactiva.
7. Usuario intenta trasladar una mesa perteneciente a otro Punto de Venta.
8. Dos meseros intentan mover la misma cuenta al mismo tiempo.
9. Doble clic sobre "Reasignar".
10. Error de BD a mitad del traslado:
    - no debe quedar la venta apuntando a una mesa y el estado visual de la otra mesa en otro estado.
11. La comanda ya tiene tickets impresos:
    - no duplicarlos.
12. Existen varias rondas de pedidos:
    - todas deben seguir vinculadas a la misma venta.
13. El navegador conserva una pantalla antigua:
    - el backend debe volver a validar el estado actual antes de confirmar.
14. Mesa origen ya fue liberada/cerrada por otro usuario:
    - rechazar el traslado con mensaje controlado.

**Pruebas mínimas**
- traslado válido;
- destino ocupado rechazado;
- destino inexistente rechazado;
- traslado entre locales rechazado;
- doble ejecución no duplica ni rompe la cuenta;
- rondas y total permanecen intactos;
- origen queda libre y destino ocupada;
- tickets anteriores no se duplican.

---

#### RF07 — PRECIOS ESPECIALES DURANTE LA VENTA / CONVENIOS

**Objetivo funcional**
Permitir aplicar un valor especial autorizado al momento de vender, sin alterar permanentemente el precio base del producto.

**Reutilización permitida de funciones extra**
- La lógica existente de QR/convenios puede conservarse únicamente como apoyo opcional.
- El concepto debe generalizarse como `Convenio / Beneficio Autorizado`, no depender de cabaña, huésped o desayuno.
- No seguir ampliando OfertaTemporada mientras no sea necesaria para RF07.

**Reglas de negocio recomendadas**
- El precio oficial del producto se obtiene desde BD.
- Un precio especial afecta solo la venta/detalle autorizado, no el precio maestro de `Producto`.
- Registrar, usando la estructura existente o la mínima ampliación necesaria:
  - precio original;
  - precio aplicado;
  - usuario que autorizó/aplicó;
  - motivo/convenio cuando corresponda;
  - fecha/hora.
- Verificar si el modelo `PrecioEspecial` existente puede resolver esto antes de crear nuevos campos/modelos.

**Escenarios problemáticos obligatorios**
1. Precio especial igual a cero o negativo.
2. Precio especial superior/inferior fuera de política definida.
3. Cajero intenta modificar precio sin permiso.
4. Convenio inexistente/inactivo/vencido si el sistema utiliza convenios.
5. Código/QR reutilizado cuando el beneficio deba ser de un solo uso.
6. Aplicación doble del mismo beneficio.
7. El navegador manipula el precio enviado por JSON.
8. El precio base cambia en BD mientras el cajero tiene una pantalla antigua.
9. Venta anulada después de aplicar precio especial:
   - la trazabilidad debe conservar qué ocurrió.
10. Varios productos con distintos precios especiales en la misma venta.
11. Error durante el cobro:
   - no dejar detalle vendido sin venta consistente.

**Pruebas mínimas**
- precio normal;
- precio especial autorizado;
- modificación no autorizada rechazada;
- valor negativo/cero rechazado;
- precio enviado por cliente ignorado/revalidado;
- trazabilidad del cambio conservada.

---

#### RF10 — CONSUMO INTERNO / FIADO DEL PERSONAL

**Objetivo funcional**
Registrar productos consumidos por trabajadores como consumo interno, manteniendo detalle y monto acumulado para gestión posterior.

**Modelo existente a reutilizar**
Antes de crear estructuras nuevas, revisar y utilizar:
- `ConsumoInterno`;
- `DetalleConsumoInterno`;
- usuario/trabajador existente;
- Producto;
- PuntoVenta.

**Comportamiento esperado**
- Seleccionar trabajador interno válido.
- Agregar uno o varios productos.
- Registrar cantidades, valores aplicables, fecha/hora y Punto de Venta.
- Calcular monto total en servidor.
- Consultar historial y acumulado por trabajador.
- No mezclar consumo interno con una venta normal de cliente.

**Escenarios problemáticos obligatorios**
1. Trabajador inexistente.
2. Trabajador inactivo.
3. Producto inexistente/inactivo.
4. Cantidad cero o negativa.
5. Doble envío del mismo consumo.
6. Precio manipulado desde navegador.
7. Usuario intenta registrar consumo interno de otro local sin autorización.
8. Error después de crear encabezado pero antes de crear detalles:
   - rollback completo.
9. Producto queda inactivo después de abrir la pantalla pero antes de confirmar.
10. Eliminación de trabajador con consumos históricos:
    - conservar historia.
11. Consulta de acumulados:
    - no contar consumos anulados si en el futuro existe esa condición.

**Pruebas mínimas**
- consumo válido;
- acumulado correcto;
- trabajador inválido/inactivo rechazado;
- producto inválido rechazado;
- doble envío controlado;
- rollback ante error;
- historial permanece disponible.

---

#### RF13 + RF16 — ENTREGA DE PRODUCTOS Y TIEMPOS DE ATENCIÓN

**Objetivo funcional**
Cerrar el ciclo Pedido -> Preparación -> Listo -> Entregado y generar tiempos reales para estadísticas.

**Datos mínimos que deben poder obtenerse**
- hora de generación del pedido;
- hora de inicio de preparación si existe;
- hora de estado LISTO;
- hora de entrega al cliente;
- tiempo de preparación;
- tiempo desde pedido hasta entrega.

**Integración con KDS**
- COCINERO cambia estados de preparación.
- MESERO/CAJERO registra entrega cuando corresponde.
- Utilizar `Entrega` y estructuras existentes antes de crear modelos nuevos.

**Escenarios problemáticos obligatorios**
1. Marcar entregado un pedido que todavía está pendiente.
2. Marcar entregado dos veces.
3. Pedido con varios tickets (Cocina y Barra) listos en momentos distintos.
4. Entrega parcial:
   - definir claramente si el sistema registra entrega por pedido completo, ticket o producto según estructura real.
   - no inventar granularidad sin revisar modelos.
5. Segunda ronda de la misma mesa:
   - los tiempos deben pertenecer a su pedido/ronda correcta.
6. Ticket cancelado/anulado:
   - no contarlo como entrega normal.
7. Hora del servidor y zona horaria:
   - usar `America/Santiago`.
8. Actualización simultánea desde Cocina y Mesero.
9. Navegador intenta forzar un estado inválido.
10. Caída entre cambio de estado y registro de Entrega:
    - evitar estados incoherentes.

**Pruebas mínimas**
- flujo normal completo;
- transición inválida rechazada;
- doble entrega rechazada;
- tiempo calculado no negativo;
- rondas separadas correctamente;
- datos disponibles para RF16/RF18.

---

#### RF17 — GESTIÓN DE OCUPACIÓN DE MESAS

**Objetivo funcional**
Medir cuánto tiempo permanece utilizada una mesa desde el inicio de la atención hasta su liberación.

**Reglas**
- Una mesa pasa a ocupada cuando comienza una atención válida.
- Una nueva ronda NO reinicia el tiempo de ocupación.
- Reasignar una venta debe cerrar correctamente la ocupación de la mesa origen e iniciar/continuar la ocupación en la mesa destino según la decisión técnica que se documente.
- La mesa no puede liberarse si conserva una venta/cuenta abierta.
- Al pagar/cerrar la cuenta, la mesa puede pasar a disponible según el flujo operativo definido.
- No inventar nuevos estados de mesa sin revisar primero los estados actuales del modelo.

**Escenarios problemáticos obligatorios**
1. Intento de liberar mesa con cuenta abierta.
2. Intento de ocupar mesa ya ocupada.
3. Dos meseros toman la misma mesa al mismo tiempo.
4. Cierre de cuenta falla:
   - no liberar mesa prematuramente.
5. Cambio de mesa durante la atención.
6. Jornada cambia de día con una mesa todavía marcada ocupada.
7. Venta anulada/cancelada.
8. Mesa desactivada administrativamente mientras está ocupada:
   - bloquear acción o resolver de forma controlada.
9. Reinicio del navegador:
   - estado debe reconstruirse desde BD, no depender del frontend.

**Pruebas mínimas**
- ocupación normal;
- múltiples rondas no reinician atención;
- cierre libera mesa;
- cuenta abierta impide liberar;
- concurrencia impide doble ocupación;
- reasignación conserva coherencia.

---

#### RF18 — REPORTES Y ESTADÍSTICAS REALES

**Objetivo funcional**
Generar reportes exclusivamente desde datos persistidos reales.

**Mínimos requeridos por docente**
- ventas realizadas;
- productos más vendidos;
- tiempos de espera y entrega.

**Agregar únicamente si los datos reales existen**
- ocupación/duración de mesas;
- ventas por Punto de Venta;
- ventas por cajero;
- consumos internos;
- tiempos Cocina/Barra.

**Reglas**
- No usar datos demo/mocks como si fueran reportes reales.
- Definir filtros por rango de fecha y Punto de Venta cuando corresponda.
- Las cifras deben obtenerse mediante consultas ORM/SQL reales.
- Los totales deben considerar correctamente anulaciones/cancelaciones si dichas entidades/estados existen.
- No mezclar ventas normales con consumo interno salvo que el reporte lo indique expresamente.

**Escenarios problemáticos obligatorios**
1. Día sin ventas -> mostrar cero, no error.
2. Rango de fechas inválido.
3. Fecha inicio > fecha fin.
4. Local sin datos.
5. Producto eliminado/desactivado con historial:
   - debe seguir apareciendo en históricos cuando corresponda.
6. Ventas con precio especial.
7. Ventas rápidas vs mesas.
8. Pedidos sin entrega todavía:
   - no inventar tiempo de entrega.
9. Datos históricos de otra jornada.
10. Zona horaria y cambio de día.
11. Gran cantidad de registros:
    - evitar consultas N+1 y tiempos excesivos.

**Pruebas mínimas**
- ventas totales correctas;
- ranking de productos correcto;
- tiempos calculados solo con registros válidos;
- filtros de fechas;
- resultado vacío controlado;
- datos únicamente reales.

---

### SITUACIONES TRANSVERSALES QUE EL SISTEMA DEBE SOPORTAR

Estas situaciones deben considerarse en todos los RF restantes:

1. **Doble clic / doble envío**
   - no duplicar ventas, pedidos, consumos, entregas ni reasignaciones.

2. **Concurrencia**
   - dos cajeros/meseros/cocineros actuando sobre el mismo recurso no deben provocar corrupción de datos.

3. **Pérdida de conexión o error de servidor**
   - la operación debe completarse entera o revertirse entera cuando sea transaccional.

4. **Datos manipulados desde navegador**
   - IDs, precios, cantidades, roles y locales deben revalidarse en servidor.

5. **Registro eliminado/desactivado mientras otro usuario trabaja**
   - volver a consultar estado antes de confirmar.

6. **Sesión vencida durante una operación**
   - no realizar cambios sin autenticación válida.

7. **Usuario sin permisos**
   - responder 403/control equivalente y no procesar la acción.

8. **Ruta o ID inexistente**
   - responder 404 amigable, no excepción sin manejar.

9. **Día/jornada**
   - no reutilizar automáticamente una jornada antigua como si fuera la actual.

10. **Impresora física no disponible**
    - RF09 sigue en modo digital provisional; fallo de impresión no debe destruir la venta ya registrada.
    - cuando exista impresión física, separar claramente persistencia de venta y reimpresión de ticket.

11. **Integridad histórica**
    - desactivar/soft-delete cuando corresponda en vez de destruir ventas, pedidos, consumos o reportes históricos.

12. **Auditoría**
    - operaciones sensibles deben poder atribuirse a usuario, fecha/hora y local cuando la estructura actual lo permita.

13. **Mensajes al usuario**
    - explicar el problema y permitir recuperación; no mostrar detalles técnicos internos.

---

### ORDEN DE EJECUCIÓN AUTORIZADO
1. Auditar implementación actual exacta de RF05.
2. Implementar/cerrar RF05 con pruebas.
3. Detener y devolver `AI_CONTEXT.md` para revisión de ChatGPT/usuario.
4. Solo después avanzar RF07.
5. Repetir el mismo ciclo para RF10, RF13/16, RF17 y RF18.

**No ejecutar todos los RF restantes de una sola vez.**
La implementación seguirá siendo incremental para detectar regresiones y mantener trazabilidad.

---
### PLAN ACADÉMICO DE RECUPERACIÓN — SEMANA 10 Y AVANCE SEMANA 11

#### Semana 10 — Clase 13/10/2026 — DEBE QUEDAR COMPLETA
Contenido solicitado por docente:
- Creación de proyecto Django.
- Inicio de sesión con cuentas de usuarios desde BD según perfil.
- Validación de campos de inicio de sesión.
- Investigación e implementación de personalización para errores:
  - 404.
  - 500.
  - errores de rutas/URL.
  - errores de servidor.
  - otros escenarios controlables.
- Validaciones necesarias para enfrentar escenarios complejos de vulnerabilidad y caídas.

Estado actual frente a Semana 10:
- Proyecto Django: YA EXISTE.
- Login real desde BD: YA EXISTE.
- Perfiles/roles actuales: ADMINISTRADOR, CAJERO, MESERO y COCINERO.
- Validaciones de credenciales, usuario inactivo y aislamiento de roles: YA EXISTEN.
- Falta dejar completamente demostrable y testeado el bloque de manejo de errores y robustez/vulnerabilidades.

#### Orden técnica Semana 10
1. **Auditar login y permisos existentes**
   - Confirmar validación de campos vacíos.
   - Confirmar credenciales inválidas.
   - Confirmar usuario/perfil inactivo.
   - Confirmar bloqueo de acceso directo a rutas de otro rol.
   - Confirmar que el rol real siempre proviene de la sesión/perfil en BD y no de parámetros del navegador.
   - Mantener los 4 roles vigentes.

2. **Personalizar errores HTTP**
   - Crear/verificar templates propios y coherentes con Parque Safari para:
     - `404.html`
     - `500.html`
   - Configurar `handler404` y `handler500` correctamente si aún no existen.
   - Verificar comportamiento con `DEBUG=False` en un entorno de prueba seguro.
   - No mostrar stack traces ni información sensible al usuario final.
   - Para errores de rutas/URL, mostrar 404 amigable en vez de error técnico.
   - Para error interno de servidor, mostrar 500 amigable con opción de volver al inicio/login.

3. **Validaciones de robustez y vulnerabilidad**
   Verificar y completar, sin sobredimensionar:
   - CSRF en formularios POST.
   - Control de métodos HTTP.
   - Acceso no autorizado por URL.
   - IDs inexistentes/manipulados.
   - Relaciones inexistentes o PuntoVenta no asignado.
   - Valores numéricos inválidos/negativos cuando corresponda.
   - `ProtectedError` y eliminaciones protegidas.
   - Operaciones críticas dentro de `transaction.atomic()` donde ya corresponde.
   - No confiar en rol, precio, local o identidad enviados por JavaScript cuando exista fuente de verdad en servidor/BD.
   - Mensajes de error controlados sin exponer información interna.

4. **Pruebas Semana 10**
   Agregar únicamente las pruebas que falten para poder demostrar:
   - 404 personalizado.
   - acceso no autorizado por rol.
   - campos inválidos/vacíos de login.
   - usuario inactivo.
   - petición con identificador inexistente no derriba el servidor.
   - protección CSRF o método HTTP según corresponda.
   - 500 personalizado: validado de forma controlada y blindada.
   - Rate limiting y Fuerza Bruta: bloqueo temporal de 5 minutos tras 5 intentos fallidos consecutivos.
   - Cabeceras HTTP y Cookies Seguras: X-Frame-Options DENY, X-Content-Type-Options nosniff, HttpOnly, SameSite Lax, expiración de sesión por cierre de navegador y timeout a 8h.
   - Criptografía de contraseñas: PBKDF2/Argon2 y longitud mínima de seguridad (>=6 para colaboradores).
   - Sanitización de datos: prevención contra manipulación de cantidades y precios negativos en comandas y validación de IDs numéricos.
   - Suite de pruebas: **37 pruebas automatizadas aprobadas al 100% (Ran 37 tests OK)**.

---

#### Semana 11 — Clase 20/10/2026 — AVANZAR PARCIALMENTE
Contenido solicitado por docente:
- CRUD básicos con BD:
  - Gestión de Usuarios.
  - Gestión de Mesas.
  - Gestión de Puntos de Venta.
  - Gestión de Menús.
  - Gestión de Productos.
  - Historial de Acciones realizadas.
- Validaciones de campos.
- Validaciones frente a vulnerabilidades/caídas.

#### Qué debe quedar adelantado antes de la clase del 20/10
1. **Gestión de Usuarios**
   - No rehacer.
   - Consolidar el CRUD existente de trabajadores/usuarios como evidencia de Semana 11.
   - Confirmar crear, listar/buscar, modificar, activar/desactivar y manejo de contraseña.
   - Confirmar validaciones y permisos de Administrador.

2. **Gestión de Puntos de Venta**
   - No rehacer.
   - Consolidar el CRUD existente como segunda evidencia real de Semana 11.
   - Confirmar crear, modificar, activar/desactivar/eliminar protegido.
   - Confirmar que un local con historial no pierde datos.

3. **Gestión de Mesas — CRUD NUEVO PRIORITARIO (COMPLETADO AL 100%)**
   - Implementado en `/administrador/mesas/` accesible exclusivamente por rol `ADMINISTRADOR`.
   - Funciones operativas:
     - Listar mesas por Punto de Venta / Local con filtros y búsqueda por texto.
     - Crear mesa (identificador, Punto de Venta, capacidad, estado).
     - Modificar identificador, Punto de Venta asignado, capacidad y estado.
     - Activar/desactivar mesa (`toggle_estado`) para mantenimiento.
     - Validación estricta de unicidad de identificador por local (`unique_together`).
     - Protección de cuentas abiertas: No permite desactivar ni eliminar mesas con comanda en consumo.
     - Eliminación segura: Si la mesa tiene ventas históricas, se desactiva (soft-delete) para preservar integridad contable; si no tiene historial, se elimina limpiamente.
     - Cobertura de pruebas: Pruebas unitarias 38, 39, 40 y 41 aprobadas al 100% (41/41 tests OK).

4. **Productos y Menús — GESTIÓN CON BD (COMPLETADO AL 100%)**
   - Implementado en `/administrador/productos/` y `/administrador/menus/`, accesible solo para `ADMINISTRADOR`.
   - Lee y gestiona datos reales directamente desde la base de datos (modelos `Producto`, `Categoria`, `Menu`, `PuntoVenta`).
   - Funciones operativas:
     - Listar productos con filtros por categoría, local asignado y búsqueda por nombre/código.
     - Crear nuevo producto con precio, categoría y punto de venta opcional.
     - Modificar producto (nombre, precio, categoría, punto de venta).
     - Activar/desactivar producto (`toggle_estado`) para disponibilidad operativa.
     - Eliminación contablemente segura: Si el producto registra ventas históricas (`DetalleVenta` o `DetallePedido`), se aplica soft-delete (`activo=False`) para no destruir la auditoría fiscal ni balances; si no registra ventas, se borra físicamente.
     - Gestión de Menús: Listar cartas por Punto de Venta, creación de cartas asociadas a locales y vinculación múltiple de productos reales.
     - Cobertura de pruebas: Pruebas unitarias 42, 43, 44 y 45 agregadas y aprobadas al 100% (**45/45 tests OK**).
   - Seeding y persistencia: Comando oficial `poblar_safari` actualizado con categorías oficiales (5), productos representativos (16) y menús por local (3), manteniendo idempotencia.
   - Regla de no regresión respetada: Las terminales de Mesero y Cajero no sufrieron alteraciones en sus flujos operativos.

5. **Historial de Acciones y Trazabilidad Operativa (COMPLETADO AL 100%)**
   - Implementado en `/administrador/historial/`, accesible exclusivamente por rol `ADMINISTRADOR`.
   - Lee y consolida eventos reales directamente desde la base de datos (modelos `Jornada`, `Caja`, `AlertaTraslado`, `Venta`, `Entrega`), sin necesidad de añadir tablas artificiales ni migraciones complejas.
   - Funciones operativas:
     - Línea de tiempo cronológica descendente con Ref. ID, marca de tiempo (`fecha_hora`), badge de acción, descripción detallada, local y usuario responsable.
     - Filtro por tipo de evento (Jornadas, Cajas, Traslados de Personal, Ventas Gastronómicas, Entregas Cocina KDS).
     - Filtro por Punto de Venta / Local.
     - Búsqueda libre por texto (nombre de usuario, ID de referencia, local o descripción).
     - Indicadores KPI superiores en tiempo real (Total Eventos, Jornadas, Cajas, Traslados, Ventas, Cocina KDS).
     - Enlace integrado en la barra de navegación del Administrador en todos los módulos.
   - Cobertura de pruebas: Pruebas unitarias 48, 49 y 50 agregadas y aprobadas al 100% (**50/50 tests OK**).

#### Criterio de llegada a clase del 20/10 — COMPLETADO AL 100%
- Semana 10: 100% demostrable (Login por perfiles, Rate Limiting, OWASP, 404/403/400/500 personalizados sin stack traces).
- Semana 11:
  - Usuarios: CRUD real existente y validado.
  - Puntos de Venta: CRUD real existente y validado.
  - Mesas: CRUD completo con protección de comanda abierta y soft-delete contable.
  - Productos/Menús: CRUD completo conectado a BD por local.
  - Historial de Acciones: Bitácora completa y funcional con eventos reales de BD.
- Suite oficial: **50 pruebas unitarias aprobadas al 100% (Ran 50 tests OK)**.
- Sin regresiones: KDS Cocina, Mesa/Cuenta Abierta, Caja, roles y responsive móvil 100% estables.

---
### RECORDATORIO URGENTE PARA EL SIGUIENTE INFORME (ENTREGA 3 - PUNTO 4 Y DOCUMENTACIÓN)
> [!IMPORTANT]
> **No modificar documentos Word antiguos.** Todo lo listado a continuación se aplicará directamente sobre el **NUEVO INFORME** de la Entrega 3 cuando el usuario indique su inicio:
>
> 1. **Sincronización del Modelo Lógico 1:1 con `models.py` (Rúbrica 2.1.4.8 - 10 Puntos):**
>    - En el nuevo informe, el diagrama relacional debe contener las **19 entidades completas** implementadas en Django y en el script físico DDL:
>      - `auth_user`, `perfil_empleado` (con rol `COCINERO`), `alerta_traslado`.
>      - `punto_venta`, `jornada`, `caja`.
>      - `mesa`, `categoria`, `producto`, `precio_especial`, `menu`.
>      - `venta`, `detalle_venta`.
>      - `pedido`, `detalle_pedido`, `ticket`, `entrega`.
>      - `consumo_interno`, `detalle_consumo_interno`.
>    - Ejecutar `generar_word_modelo_datos.py` para compilar el diagrama en alta resolución 300 DPI (`diagrama_erd_parque_safari.png`) con enrutamiento ortogonal limpio (sin líneas que crucen cajas ni tapen texto).
>    - Reemplazar la imagen en el nuevo documento Word asegurando proporción panorámica (ancho ~6.4 in, alto ~4.05 in) para que no se deforme ni borre.
>    - En el script SQL físico dentro del informe, verificar que `chk_rol_valido` incluya `'COCINERO'`.
>    - Incluir el diccionario descriptivo de las 19 tablas con sus PK, FK, tipos y restricciones.
>
> 2. **Enlace al Proyecto Azure DevOps (Rúbrica 2.1.1.2):**
>    - Incluir de forma destacada e hipervinculada en la portada y en la Sección de Planificación el enlace público/lector de Azure DevOps:
>      `https://dev.azure.com/[organizacion]/[proyecto]`.
>
> 3. **Redacción Estrictamente Impersonal en Paradigma 4+1 (Rúbrica 2.1.2.3):**
>    - Sustituir cualquier conjugación en primera persona (*"nos permite"*, *"nos permitirán"*, *"nuestro sistema"*) por redacción impersonal técnica (*"el modelo permite"*, *"la arquitectura posibilita"*, *"el sistema desarrollado"*).
>
> 4. **Plantilla Oficial de Retroalimentación de Pares (Rúbrica 2.1.3.7):**
>    - Utilizar e incorporar en el cuerpo del informe la plantilla oficial de la Semana 7 facilitada por el docente evaluador.
>
> 5. **Buenas Prácticas de Codificación Segura y Estándares:**
>    - Redactar secciones de: Buenas prácticas generales (OWASP Top 10, CWE), Estándares reconocidos (PEP 8, ISO/IEC 25010), y Políticas internas (Cero credenciales en código, RBAC estricto, inmutabilidad de perfiles).
>
> 6. **Detalle del Plan de Pruebas (Unitarias y Herramientas):**
>    - 12.1 Pruebas Unitarias: Documentar funciones (ej. `comprobar_id`, `cambiar_estado_pedido`), resultados esperados (positivos/negativos) e impacto en templates.
>    - 12.2 Herramientas: Describir pruebas de caja blanca, caja negra, PyTest, Django TestCase, coverage.

---

### Calificación Oficial Informe 2: **78,70 / 100,00**
* **Fecha de Calificación:** Lunes, 12 de octubre de 2026, 17:33 hrs.
* **Evaluador:** Prof. Miguel Angel López Jerez (INACAP).
* **Comentario Textual de Retroalimentación del Docente:**
  > *"El proyecto presenta un desarrollo considerable. Existe una interfaz de inicio de sesión con usuario y contraseña, las rutas están realmente definidas en urls.py y las vistas correspondientes se encuentran implementadas en views.py.*
  > *También existe diferenciación real de perfiles Administrador, Cajero y Mesero, y el nombre del usuario autenticado aparece en las interfaces correspondientes. El informe, además, describe explícitamente estos perfiles y sus responsabilidades.*
  > ***Existe una diferencia importante respecto de la problemática: no se presenta un perfil/interfaz independiente para Cocina/Cocinero.***
  > *El mesero puede preparar la comanda y el proyecto contempla tickets dirigidos a Cocina y Barra, pero falta una interfaz propia donde el cocinero pueda visualizar los pedidos pendientes, cambiar su estado y dejar disponible para el garzón/mesero la información de que el pedido ya está preparado.*
  > *El modelo relacional presentado contiene PK, FK y relaciones entre las principales entidades. Además, el script físico es considerablemente más amplio e incorpora integridad referencial, restricciones CHECK, UNIQUE, relaciones y diferentes políticas ON DELETE.*
  > ***Sin embargo, el modelo lógico presentado gráficamente no representa la totalidad de la estructura que posteriormente aparece en el modelo físico y en models.py.*** *La implementación Django contiene, entre otras, entidades para pedidos, detalles de pedidos, tickets, entregas, consumos internos y alertas de traslado que amplían considerablemente el modelo."*

A continuación se registra el desglose completo de observaciones, brechas y acciones correctivas derivadas de la calificación del segundo informe, organizadas por criterio y prioridad técnica para la tercera entrega:

### 1. [2.1.4.9] Configuración del Motor de Base de Datos (PostgreSQL / MySQL) [URGENTE - CRÍTICO]
- **Puntaje Obtenido:** 1.95 / 5.0 pts (En desarrollo)
- **Observación Docente:** *"settings.py mantiene la configuración predeterminada de SQLite y no presenta la conexión requerida a MySQL. El informe propone PostgreSQL, pero esta configuración tampoco se encuentra aplicada en el proyecto entregado."*
- **Nota del Usuario:** *"esto debemos ver urgente"*.
- **Acción Requerida para Entrega 3:**
  - Configurar en `Venta_safari/settings.py` el soporte formal para PostgreSQL / MySQL mediante variables de entorno (`DATABASE_URL` o bloque `DATABASES` dinámico).
  - Incluir el adaptador correspondiente (`psycopg2-binary` para PostgreSQL y/o `mysqlclient`/`PyMySQL` para MySQL) en `requirements.txt`.
  - Proveer un fallback condicional inteligente a SQLite para desarrollo local sin servidor activo, pero asegurando que la configuración formal por defecto del proyecto apunte a PostgreSQL/MySQL tal como lo declara el informe y el modelo físico.
  - Asegurar coherencia entre el texto del informe (que menciona PostgreSQL en infraestructura y script DDL) y `settings.py`.

### 2. [2.1.3.5] Interfaz Específica para Cocina / Cocinero (KDS - Kitchen Display System) [ALTA PRIORIDAD]
- **Puntaje Obtenido:** 3.65 / 5.0 pts (Habilitado)
- **Observación Docente:** *"El prototipo presenta login, perfiles, navegación, ventas, caja, mesas, comandas, tickets, administración y reportes. Sin embargo, falta una interfaz específica para Cocina/Cocinero que permita visualizar pedidos pendientes, gestionar su preparación y comunicar al mesero cuáles están listos para ser servidos."*
- **Acción Requerida para Entrega 3:**
  - Crear la vista y plantilla dedicada para Cocina (`/cocina/` / `cocina.html` / KDS):
    - Visualización en tarjetas táctiles (tipo Kanban) de pedidos entrantes clasificados por destino (`COCINA` vs `BARRA`).
    - Flujo de estados interactivo: `PENDIENTE` -> `EN PREPARACIÓN` -> `LISTO PARA ENTREGA`.
    - Botón de acción para el cocinero (*"Comenzar Preparación"*, *"Marcar Plato Listo"*).
    - Notificación visual/comunicación al módulo de Mesero para alertar que los platos de la mesa están listos para ser retirados y servidos.
  - Agregar nuevo rol o perfil específico de Cocinero / Jefe de Cocina si aplica, o permitir acceso operativo de cocina.

### 3. [2.1.5.12] Coherencia en "Cero Credenciales en Código" (SECRET_KEY en settings.py) [ALTA PRIORIDAD]
- **Puntaje Obtenido:** 7.3 / 10.0 pts (Habilitado)
- **Observación Docente:** *"Los estándares están ampliamente desarrollados; sin embargo, el informe establece explícitamente una política de 'Cero Credenciales en Código' que prohíbe mantener SECRET_KEY directamente en los archivos, mientras que settings.py mantiene esta clave escrita en el código. Debe existir coherencia entre los estándares definidos y su aplicación."*
- **Nota del Usuario:** *"debemos ajuntar"*.
- **Acción Requerida para Entrega 3:**
  - Extraer `SECRET_KEY` de `Venta_safari/settings.py` utilizando `os.environ.get('SECRET_KEY')` o biblioteca de variables de entorno (`python-dotenv` / `decouple`).
  - Crear archivo `.env.example` en la raíz del repositorio con variables de muestra.
  - Verificar que el archivo `.env` real esté explícitamente protegido y excluido en `.gitignore`.
  - Asegurar coherencia absoluta entre las políticas redactadas en el informe y los archivos del repositorio.

### 4. [2.1.6.13] Documentación y Ejecución de Pruebas de Rendimiento (Performance Testing) [ALTA PRIORIDAD]
- **Puntaje Obtenido:** 7.3 / 10.0 pts (Habilitado)
- **Observación Docente:** *"Se presentan y ejecutan pruebas unitarias y de integración, pero falta desarrollar y documentar con la misma claridad un conjunto específico de pruebas de rendimiento."*
- **Nota del Usuario:** *"debemos aclarar mas esto"*.
- **Acción Requerida para Entrega 3:**
  - Desarrollar, ejecutar y documentar formalmente pruebas de rendimiento (*Performance / Load Testing*):
    - Medición de latencia y tiempos de respuesta (ms) en endpoints críticos: Login, creación de comanda en mesero, despacho de tickets, consulta de dashboard con 15 meses de transacciones.
    - Simulación de carga concurrente (ej. 20, 50, 100 usuarios simultáneos en hora pico de Parque Safari) utilizando herramientas como Locust, k6, Apache Benchmark (`ab`) o script automatizado de benchmarking en Python.
    - Incluir en el informe una sección y tabla formal de resultados de rendimiento: tiempo de respuesta promedio, percentil 95, rendimiento de peticiones por segundo (RPS), consumo de CPU y memoria RAM.

### 5. [2.1.4.8] Sincronización Completa entre Modelo Lógico (Draw.io) y Físico (models.py) [MEDIA-ALTA PRIORIDAD]
- **Puntaje Obtenido:** 7.3 / 10.0 pts (Habilitado)
- **Observación Docente:** *"El modelo presenta correctamente entidades, claves y relaciones; sin embargo, el modelo lógico no representa completamente todas las entidades y relaciones que posteriormente aparecen implementadas en models.py y en el modelo físico."*
- **Acción Requerida para Entrega 3:**
  - Actualizar el diagrama relacional en Draw.io para que represente el 100% de las tablas declaradas en el script SQL y en `ventas/models.py`.
  - Entidades a sincronizar e incorporar en el diagrama de Draw.io:
    - `AlertaTraslado` (relacionada con `auth_user` y `punto_venta` origen/destino).
    - `PrecioEspecial` (relacionada con `producto`).
    - `Menu` y tabla intermedia `MenuProductos` / `ProductoPuntosVenta`.
    - `Entrega` (relacionada con `pedido`, `ticket` y `auth_user`).
    - `ConsumoInterno` y `DetalleConsumoInterno` (relacionada con `auth_user`, `punto_venta` y `producto`).
  - Reemplazar la imagen en el informe garantizando que modelo lógico, modelo físico y `models.py` sean un reflejo espejo 1:1.

### 6. [2.1.1.2] Enlace al Proyecto de Azure DevOps en el Informe [RECORDATORIO FORMATO]
- **Puntaje Obtenido:** 1.95 / 5.0 pts (En desarrollo)
- **Observación Docente:** *"En el informe NO se evidencia el enlace para acceder y lograr revisar el proyecto en Azure DevOps."*
- **Nota del Usuario:** *"este fue mi error asi que recordatorio"*.
- **Acción Requerida para Entrega 3:**
  - Agregar de forma visible y destacada en el informe (en la portada, en la introducción y en la sección 2.2 de Azure DevOps) el enlace directo hipervinculado a la organización y proyecto de Azure DevOps:
    `https://dev.azure.com/[organizacion]/[proyecto]`
  - Verificar que el enlace posea permisos públicos o que el usuario docente (`Miguel Angel López Jerez`) tenga concedidos los permisos de lectura (*Stakeholder* / *Basic*).

### 7. [2.1.2.3] Redacción Estrictamente Impersonal en Paradigma 4+1 [CORRECCIÓN FORMATO]
- **Puntaje Obtenido:** 3.65 / 5.0 pts (Habilitado)
- **Observación Docente:** *"Las cinco vistas están desarrolladas; sin embargo, se utilizan expresiones en primera persona como 'nos permite' y 'nos permitirán'. La redacción del informe debe mantenerse de manera impersonal."*
- **Acción Requerida para Entrega 3:**
  - Realizar un barrido ortotipográfico y estilístico completo en el informe, erradicando toda conjugación en primera persona ("nos permite", "hicimos", "definimos", "nuestro sistema").
  - Sustituir por redacción técnica impersonal y pasiva refleja: *"el modelo permite"*, *"la arquitectura posibilita"*, *"se define"*, *"se implementó"*, *"el sistema desarrollado"*.

### 8. [2.1.3.7] Plantilla Oficial de Retroalimentación de Pares [GESTIÓN ACADÉMICA]
- **Puntaje Obtenido:** 1.95 / 5.0 pts (En desarrollo)
- **Observación Docente:** *"El formato con los comentarios de las revisiones a modo de retroalimentación por parte de otros equipos, NO es la facilitada por el docente."*
- **Nota del Usuario:** *"esto debo charlar con el docente porque si le abjunte en un archvio aparte"*.
- **Acción Requerida para Entrega 3:**
  - Aclarar con el docente la entrega previa del archivo adjunto.
  - Transcribir e insertar la información directamente dentro de la plantilla oficial de la Semana 7 facilitada por el profesor, incorporándola de manera visible en el cuerpo principal del informe.

### 9. [2.1.6.15] Registro y Presentación Continua de Avances en Clases [SEGUIMIENTO]
- **Puntaje Obtenido:** 3.65 / 5.0 pts (Habilitado)
- **Observación Docente:** *"Existen semanas de clases donde no se presentan los avances requeridos por el docente."*
- **Acción Requerida para Entrega 3:**
  - Mantener al día la bitácora semanal y presentar puntualmente los avances en cada sesión de clase presencial según el calendario del curso.

---

## 3. estado actual
- estado: Servidor de desarrollo activo en http://127.0.0.1:8000/. Código limpio con 0 incidencias (`manage.py check`) y suite de **25 pruebas automatizadas oficiales (`ventas/tests.py`) aprobadas al 100% (25/25 OK)**.
- último avance: **Horario Oficial (10:00 - 18:00) y Reinicio Automático Diario de Tickets y Cuentas a 0**:
  - **Horario Oficial de Operación (10:00 a 18:00 hrs)**:
    - En `ventas/views.py`: Se calculan `hora_apertura = time(10, 0)`, `hora_cierre = time(18, 0)` y `en_horario = (10:00 <= ahora_hora < 18:00)`. Se definen los turnos como `"Horario Oficial (10:00 - 18:00)"` y los estados como `"Abierto (10:00 - 18:00)"` o `"Cerrado (Horario 10:00 - 18:00)"`.
    - En plantillas (`administrador.html`, `administrador_local.html`, `vendedor.html`, `vendedor_crear_ticket.html`, `mesero.html`): Se incorporaron badges visuales dinámicos que muestran el estado operativo según la hora oficial.
  - **Reinicio Automático Diario a 0 (Guiado por Día y Hora)**:
    - Backend (`ventas/views.py`): En `get_locales_data()`, el cálculo de ventas y tickets se acota estrictamente a `fecha_hora__date=hoy`. Si un local no registra ventas hoy, arranca limpio con `$0` y `0` comandas (sin arrastrar mocks de jornadas pasadas). En `mesero`, las cuentas abiertas activas de mesas se filtran por `fecha_hora__date=hoy`.
    - Frontend (`vendedor.html` y `vendedor_crear_ticket.html`): Implementación de `STORAGE_DATE_KEY = 'safari_fecha_operativa'`. Si la fecha almacenada no coincide con la fecha actual del comensal/cajero, la memoria de tickets se purga automáticamente iniciando el día en 0 tickets y correlativo limpio `#COM-0001`.
  - **Suite Oficial de 25 Pruebas Automatizadas (`ventas/tests.py`)**:
    - 25 de 25 tests ejecutados y aprobados al 100% (`Ran 25 tests in 62.194s - OK`).
- avances previos:
  - Inmutabilidad estricta de local para meseros y optimización de pantalla móvil sin banners intrusivos.
  - Eliminación total de tickets térmicos vacíos (cero desperdicio de papel térmico) y botón ágil de despacho en hora pico.
  - Estandarización de tickets térmicos de Cocina y Barra a 80mm B&W sin emojis según boleta oficial de Parque Safari.
  - Implementación completa de Mesa/Cuenta Abierta con Pedidos Incrementales (Rondas) y Cierre de Mesa en Mesero vs. Cajero.
  - Creación dinámica de nuevos locales gastronómicos para el Administrador (`PuntoVenta` con ícono y color).
  - Unificación del Centro de Alertas en Detalle de Local con campana interactiva y descarte AJAX.
  - Creación dinámica de nuevos locales gastronómicos para el Administrador (`PuntoVenta` con ícono y color).
  - Unificación del Centro de Alertas en Detalle de Local con campana interactiva y descarte AJAX.
- último avance técnico (Auditoría RF04):
  - Inspección integral de `PuntoVenta` en `models.py`, `poblar_safari.py`, `views.py`, plantillas y scripts.
  - Levantamiento completo de dependencias en base de datos vs. mock hardcodeado (`get_locales_data()`).
  - Verificación del comportamiento de asignación por rol (Cajero estricto, Mesero flexible con fallback a Local 1 y selector manual, Administrador global).
  - Verificación de Caja (derivación desde cajero sin fallback) y Mesas (asociadas a `PuntoVenta` en BD pero no aisladas por puesto de trabajo en la UI de Mesero).
- avances previos (Fase 2A.2):
  - **Gestión Estricta de Estado Activo/Inactivo (RF01 y Seguridad)**:
    - Validación en `login_view`: Si un colaborador tiene `user.is_active=False` o `perfil.activo=False`, el acceso es rechazado informando expresamente *"Tu cuenta de colaborador se encuentra inactiva. Contacta al Administrador."*.
    - Validación en decorador `@requiere_rol`: Si un colaborador con sesión abierta es desactivado por el Administrador, en su siguiente petición es desautenticado de inmediato (`logout()`), revocado de la vista protegida y expulsado al portal inicial.
    - Reactivación verificada: Cuando el Administrador reactiva la cuenta, el colaborador puede volver a iniciar sesión y acceder a su terminal de inmediato.
  - **Preservación Segura de Contraseñas en CRUD de Trabajadores**:
    - Al editar un colaborador (`accion == 'modificar'`), si el campo de contraseña se deja vacío, la contraseña existente se conserva intacta sin regenerar ni invalidar el hash PBKDF2 previo.
  - **Integración Global de SweetAlert2 con Botones Bootstrap 5 (`static/js/safari_alerts.js`)**:
    - Erradicación total de los popups nativos del navegador (`confirm()` y `alert()`).
    - Configuración modular con botones temáticos de Bootstrap 5 (`swalWithBootstrapButtons`, `swalDangerBootstrap`, `swalWarningBootstrap` y `swalToast`).
    - Modales estilizados en `/administrador/trabajadores/` (desactivar, reactivar, eliminar con advertencia crítica), `/vendedor/` (restaurar comandas demo) y `/vendedor/nuevo-ticket/` (alerta de pedido vacío).
  - **Limpieza de Código Muerto**:
    - Retiro definitivo de la función deprecada `asegurar_locales_y_personal_bd()` de `ventas/views.py`.
  - **Suite Automatizada de 15 Pruebas Oficiales (`ventas/tests.py`)**:
    - 15 casos de prueba reproducibles ejecutables nativamente con `python manage.py test ventas`. Aprobadas al 100% sin advertencias ni regresiones.

## 4. archivos importantes
- archivo: safari_alerts.js
  - ruta: c:/Users/pc/Desktop/safari Pilar/static/js/safari_alerts.js
  - función: Módulo de SweetAlert2 estilizado con clases nativas de Bootstrap 5
  - motivo por el que es relevante: Unifica confirmaciones, alertas y toasts eliminando diálogos nativos del navegador
- archivo: AI_CONTEXT.md
  - ruta: c:/Users/pc/Desktop/safari Pilar/AI_CONTEXT.md
  - función: Memoria técnica compartida del proyecto
  - motivo por el que es relevante: Mantiene trazabilidad, reglas permanentes y sincronización entre ChatGPT y Antigravity
- archivo: tests.py
  - ruta: c:/Users/pc/Desktop/safari Pilar/ventas/tests.py
  - función: Suite oficial de pruebas automatizadas reproducibles de Django
  - motivo por el que es relevante: Cubre los 15 escenarios clave de RF01–RF03, aislamiento, fecha actual, estado activo/inactivo, preservación de credenciales, concurrencia y alternancia de estado por AJAX
- archivo: views.py
  - ruta: c:/Users/pc/Desktop/safari Pilar/ventas/views.py
  - función: Controladores optimizados sin rutinas de siembra en el ciclo HTTP
  - motivo por el que es relevante: Contiene `login_view`, `logout_view`, `abrir_jornada`, `abrir_caja`, validación de fecha local, transacciones atómicas y `@requiere_rol` con verificación de cuentas inactivas
- archivo: poblar_safari.py
  - ruta: c:/Users/pc/Desktop/safari Pilar/ventas/management/commands/poblar_safari.py
  - función: Comando administrativo idempotente de población inicial
  - motivo por el que es relevante: Puebla locales, mesas y usuarios demo faltantes sin sobrecoste en el servidor web
- archivo: anti_doble_envio.js
  - ruta: c:/Users/pc/Desktop/safari Pilar/static/js/anti_doble_envio.js
  - función: Script de interfaz para evitar envíos múltiples o clics repetidos
  - motivo por el que es relevante: Deshabilita botones al enviar formularios POST tradicionales respetando formularios AJAX
- archivo: settings.py
  - ruta: c:/Users/pc/Desktop/safari Pilar/Venta_safari/settings.py
  - función: Configuración general del proyecto
  - motivo por el que es relevante: Establece `TIME_ZONE = 'America/Santiago'` y `LANGUAGE_CODE = 'es-cl'`

## 5. cambios realizados
- cambio: Desacoplamiento total del Seeding de las Vistas HTTP
  - archivo modificado: `ventas/views.py`, `ventas/management/commands/poblar_safari.py`
  - motivo: Resolver la lentitud crítica generada por PBKDF2 en cada petición HTTP
  - resultado: Las vistas ya no ejecutan hashing ni inserciones; la población se realiza vía `python manage.py poblar_safari`. Latencia reducida de 2.500ms a 5ms
- cambio: Incorporación de Script Anti Doble Envío
  - archivo modificado: `static/js/anti_doble_envio.js`, plantillas (`index.html`, `vendedor.html`, `administrador_trabajadores.html`, `mesero.html`, `administrador.html`)
  - motivo: Impedir que clics múltiples envíen solicitudes POST repetidas
  - resultado: Botones se deshabilitan instantáneamente mostrando spinner y "Procesando...", omitiendo formularios AJAX
- cambio: Validación Estricta de Fecha Actual en Jornada Operativa
  - archivo modificado: `ventas/views.py`, `ventas/templates/ventas/vendedor.html`
  - motivo: Corregir desviación RF02; impedir que una jornada de un día anterior se reutilice hoy
  - resultado: Se consulta `fecha=timezone.localdate()`. Si hay jornada de ayer abierta, no se toma como válida y se exige apertura de hoy
- cambio: Fondo Inicial de Caja Opcional (Neutral / $0)
  - archivo modificado: `ventas/views.py`, `ventas/templates/ventas/vendedor.html`
  - motivo: Eliminar requerimiento monetario forzoso no documentado
  - resultado: Campo `monto_apertura` sin `required`, por defecto 0. Si el cajero lo deja vacío, se asume $0
- cambio: Validación de Punto de Venta Asignado al Cajero
  - archivo modificado: `ventas/views.py`, `ventas/templates/ventas/vendedor.html`
  - motivo: Eliminar fallback arbitrario a primer local de la BD
  - resultado: Si el cajero no tiene `punto_venta_actual`, se bloquea la apertura de caja y se muestra alerta informativa
- cambio: Contraseña Obligatoria Explícita en CRUD de Trabajadores
  - archivo modificado: `ventas/views.py`, `ventas/templates/ventas/administrador_trabajadores.html`
  - motivo: No dejar `safari123` como contraseña implícita de trabajadores reales
  - resultado: El administrador debe escribir obligatoriamente la contraseña al crear un colaborador
- cambio: Restricción de Base de Datos `UniqueConstraint` en Caja
  - archivo modificado: `ventas/models.py`, `ventas/migrations/0003_caja_unique_caja_por_cajero_jornada.py`
  - motivo: Garantizar a nivel de motor de BD que un cajero tenga como máximo una caja por jornada
  - resultado: Restricción única sobre `(jornada, cajero)` aplicada y migrada
- cambio: Construcción de Suite Oficial de Pruebas Automatizadas
  - archivo modificado: `ventas/tests.py`
  - motivo: Dejar suite reproducible nativa con `python manage.py test ventas`
  - resultado: 15 tests cubriendo todos los requerimientos de Fase 2A.1 y Fase 2A.2 con 100% de éxito
- cambio: Optimización Visual del Panel de Administrador (Ícono Notificador y Limpieza de Banner)
  - archivo modificado: `ventas/templates/ventas/administrador.html`
  - motivo: Reducir la saturación visual en `/administrador/`, eliminar componentes redundantes y optimizar la visibilidad de los KPIs
  - resultado: Se retiró el banner estático "Supervisión de Locales y Personal" (cuyos enlaces a Trabajadores y Dashboard ya existen en la cabecera) y se transformó el bloque expansivo del "Centro de Alertas" en un ícono notificador de campana en la barra superior con badge de alertas activas y dropdown detallado de traslados.
- cambio: Gestión Reactiva y Marcado de Alertas de Traslado (Eliminación Dinámica del Contador)
  - archivo modificado: `ventas/views.py`, `ventas/templates/ventas/administrador.html`
  - motivo: Resolver que el badge contador y las alertas no se borraban ni actualizaban al ser revisadas por el administrador
  - resultado: Se conectó el conteo a `total_alertas_no_leidas` (`leida=False`). Al abrir el desplegable de la campana (o presionar "Marcar leídas" o los checks individuales), una petición AJAX actualiza `leida=True` en SQLite, desvanece suavemente el badge rojo de la campana y conmuta el estado a "Al día" de manera instantánea y persistente.
- cambio: Renderizado Permanente de Cápsula y Aura Luminosa en Botones de Cabecera (Resolución de Caché)
  - archivo modificado: `static/css/base.css`, `ventas/templates/ventas/administrador.html`, `administrador_dashboard.html`, `administrador_trabajadores.html`, `administrador_local.html`, `vendedor_crear_ticket.html`
  - motivo: Resolver que "no se ve el coso alrededor" tras el caché de CSS en el navegador, donde la cápsula, el borde y el resplandor se perdían dejando el texto flotando.
  - resultado: Se implementó un esquema de 3 capas (especificidad con `!important` en `base.css`, cache-busting `?v=3.1` en templates y estilos de respaldo inline/locales). Los botones muestran de manera permanente su cápsula blanca, borde rojo Safari (`#a71d1d`) y un halo/aura luminoso cálido (`box-shadow: 0 0 10px rgba(167, 29, 29, 0.28)`), intensificándose al pasar el cursor sin perder legibilidad.
- cambio: Preparación de Versión para Importar y Compartir (`importar/`)
  - archivo modificado: `c:/Users/pc/Desktop/safari Pilar/importar/`, `requirements.txt`, `README.md`, `.gitignore`, `safari_pilar_completo.zip`
  - motivo: Solicitud del usuario de generar una versión completa y lista para ser importada y ejecutada por otra persona/amigo en la carpeta `importar`.
  - resultado: Se empaquetó el proyecto excluyendo cachés (`__pycache__`, `.pyc`), se añadieron `requirements.txt`, `.gitignore` y una guía detallada `README.md` con credenciales de prueba y pasos de instalación. La carpeta contiene tanto el proyecto listo para abrir y correr como un comprimido `safari_pilar_completo.zip` para envío directo.
- cambio: Publicación de Repositorio Oficial en GitHub
  - archivo modificado: `.git/`, `.gitignore`, `README.md`
  - motivo: Publicar el proyecto en la cuenta de GitHub del usuario (`F0DereckA`) como proyecto de portafolio profesional.
  - resultado: Se vinculó el remoto `origin` a `https://github.com/F0DereckA/safari-pilar.git` y se ejecutó `git push -u origin main` exitosamente. Repositorio público, limpio y en sincronía.
- cambio: Reconstrucción y Entrega de la Versión Histórica Funcional del 29 de Septiembre (`version 29 ante de retroalimentar`)
  - archivo modificado: `version 29 ante de retroalimentar/`, `test_fase2a.py`, `LEEME_INSTRUCCIONES_FOTOS.txt`, `version_29_antes_de_retroalimentar.zip`
  - motivo: Solicitud expresa del usuario de disponer de la versión funcional completa del 29 de septiembre (previa a la retroalimentación) para tomar capturas de pantalla y documentar el avance.
  - resultado: Se reconstruyó de forma fidedigna el estado del código al 29-Sep (restauración del banner `SUPERVISIÓN DE LOCALES Y PERSONAL`, Centro de Alertas como bloque en el cuerpo, alertas nativas `confirm()`, recarga completa por POST, seeding en el ciclo HTTP y validación con `test_fase2a.py` al 100% OK). Se dispuso en el proyecto y directamente en el Escritorio con instrucciones para correr en el puerto 8001.

## 6. errores actuales y observaciones pendientes
- prioridad vigente: cerrar requerimientos oficiales RF01–RF18 antes de ampliar módulos opcionales.
- pendientes principales:
  1. RF05 Reasignación de mesas: siguiente implementación/auditoría prioritaria.
  2. RF07 Precios especiales: reutilizar `PrecioEspecial` y, solo si aporta, generalizar convenios existentes sin depender de huéspedes/cabañas/desayunos.
  3. RF10 Consumo interno: consolidar flujo real usando modelos existentes.
  4. RF13/RF16 Entrega y tiempos: conectar KDS/pedidos con entrega real y mediciones.
  5. RF17 Ocupación de mesas: garantizar medición y estados coherentes.
  6. RF18 Reportes: eliminar dependencia de cualquier KPI mock y generar estadísticas reales.
- módulos opcionales congelados:
  - ConvenioHuesped;
  - ConsumoHuesped;
  - QR cabañas/desayuno;
  - OfertaTemporada.
  Permanecen funcionales pero no se amplían en esta fase.
- observación documental:
  - reconciliar conteo real vigente de tests (83 vs 84 en secciones actuales) antes del siguiente informe.
- regla de seguridad:
  - expiración de contraseña de 180 días se documenta como política interna, no como obligación específica de ISO/IEC 27400.
## 7. dudas para ChatGPT
- decisión del usuario: Entregar a Antigravity un plan completo de inicio a fin para cerrar RF07–RF18 sin omitir escenarios problemáticos.
- RF05 ya está cerrado.
- siguiente bloque real de ejecución: RF07.
- el resto de RF queda planificado en detalle, pero NO debe ejecutarse en paralelo.
## 8. respuesta de ChatGPT
- orden maestra aprobada: seguir exactamente el **PLAN MAESTRO RF07–RF18 — ORDEN COMPLETO DE INICIO A FIN** registrado al comienzo del archivo.
- regla operativa:
  - ejecutar un RF a la vez;
  - auditar primero;
  - implementar solo lo faltante;
  - blindar fallos;
  - probar;
  - actualizar este archivo;
  - detener para revisión antes del siguiente RF.
- RF actual autorizado: **RF07 Gestión de Precios durante la Venta**.
- no iniciar RF08 hasta cerrar RF07 con criterio de aceptación y suite completa.
## 9. orden actual ejecutada — Auditoría de Convergencia y Mapa de Convergencia 06-Oct

### A. Reconciliación del Estado Documental
1. **Conteo real de pruebas**: Confirmado en 20 pruebas oficiales automatizadas (15 originales + 5 nuevas añadidas para CRUD de locales, formato CLP y persistencia de comanda con notas).
2. **Listado oficial de los 20 tests en `ventas/tests.py`**:
   - `test_acceso_anonimo_bloqueado` (RF01)
   - `test_aislamiento_roles` (RF01)
   - `test_apertura_jornada_y_caja_fondo_opcional` (RF02 / RF03)
   - `test_cajero_sin_punto_venta_bloqueado` (RF03 / RF04)
   - `test_crear_nuevo_local_administrador_y_asignar_trabajador` (CRUD Locales / RF04)
   - `test_crear_trabajador_requiere_password` (RF01 / Administración)
   - `test_edicion_trabajador_sin_password_conserva_contrasena` (RF01 / Administración)
   - `test_eliminar_local_administrador` (CRUD Locales / Integridad)
   - `test_filtro_pesos_chilenos` (Formato monetario CLP global)
   - `test_jornada_ayer_no_valida_hoy` (RF02)
   - `test_login_credenciales_invalidas` (RF01)
   - `test_login_trabajador_inactivo_rechazado_y_reactivacion_permite_login` (RF01 / Seguridad)
   - `test_logout_funcional` (RF01)
   - `test_mesero_envia_comanda_y_se_refleja_en_local` (Persistencia Mesero / Trazabilidad)
   - `test_modificar_local_administrador` (CRUD Locales / RF04)
   - `test_prevencion_duplicados_jornada_y_caja` (RF02 / RF03)
   - `test_segundo_cajero_misma_jornada` (RF03)
   - `test_selector_visual_no_afecta_rol_real` (RF01 / Seguridad)
   - `test_toggle_estado_trabajador_ajax_y_post` (RF01 / Administración)
   - `test_trabajador_desactivado_con_sesion_previa_bloqueado_en_siguiente_peticion` (RF01 / Seguridad)
3. **Estado de RF04**: **PARCIALMENTE COMPLETADO / AVANZADO**.
   - El modelo `PuntoVenta` posee CRUD completo funcional en la interfaz de Administrador (`/administrador/`).
   - Los locales se crean dinámicamente en BD con ícono, color, nombre único y descripción.
   - La asignación de trabajadores a locales nuevos funciona en tiempo real.
   - La auditoría individual (`/administrador/local/<id>/`) ya no arroja error 404 para locales dinámicos.
   - *Pendiente*: Desacoplar las métricas simuladas residuales de `get_locales_data()` para que todos los KPIs deriven 100% de consultas SQL a `Venta`.

### B. Auditoría CRUD Real de `PuntoVenta`
1. **Campos reales en `ventas/models.py` (líneas 67–76)**:
   - `nombre`: CharField(max_length=100, unique=True)
   - `tipo`: CharField(max_length=50, blank=True, null=True)
   - `descripcion`: TextField(blank=True, null=True)
   - `icono`: CharField(max_length=50, default='bi-shop', blank=True)
   - `color`: CharField(max_length=20, default='#c62828', blank=True)
   - `activo`: BooleanField(default=True)
   - `creado_en`: DateTimeField(auto_now_add=True)
2. **Migración**: Registrada formalmente como `0004_puntoventa_color_puntoventa_icono.py` (aplicada y consistente).
3. **Integridad y Política de Eliminación**:
   - `eliminar_local` implementa desasignación preventiva de trabajadores (`punto_venta_actual=None`) y borrado de mesas sin ventas.
   - Si el local tiene cajas, ventas o consumos históricos protegidos (`models.PROTECT`), la vista captura de forma controlada `models.ProtectedError`, aborta la destrucción física y aplica soft-delete con `pv.activo = False`.

### C. Auditoría Persistencia de Mesero
1. **Flujo Transaccional**:
   - En `ventas/views.py` (`mesero`), la acción `enviar_comanda` opera bajo un bloque atómico estricto: `with transaction.atomic():`.
2. **Modelos creados por cada comanda**:
   - `Caja`: Recupera o crea la caja operativa del mesero en la jornada activa.
   - `Venta`: Registra monto total, mesero (`cajero=request.user`), mesa y punto de venta.
   - `Pedido`: Vinculado a la venta con estado `'EN_PREPARACION'`.
   - `DetalleVenta`: Registra cantidad, precio unitario y subtotal por producto.
   - `DetallePedido`: Persiste cantidad y **observaciones de preparación / notas libres** (`it.get('nota', '')`).
   - `Ticket`: Se crean de forma atómica e independiente por destino:
     - Si hay ítems de cocina: `Ticket(tipo_destino='COCINA', codigo='COM-COC-XXXX')`.
     - Si hay ítems de barra: `Ticket(tipo_destino='BARRA', codigo='COM-BAR-XXXX')`.
   - `Mesa`: Conmuta automáticamente su estado a `'OCUPADA'`.

### D. Auditoría Flujo Cajero / Vendedor
1. **Estado Actual**:
   - Apertura de Jornada y Caja: Persistidas en SQLite (`Jornada` y `Caja`).
   - Emisión de Tickets (`simularCobro`): Se almacena en `localStorage` del navegador (`safari_tickets_desarrollo`).
   - Monitor de Tickets: Lee de `localStorage` con fallback a datos demo.
2. **Asimetría constatada**: Mesero ya persiste transacciones reales en BD; Cajero mantiene la persistencia simulada en el cliente. La unificación del Cajero a SQLite está lista para ser implementada reutilizando el patrón atómico de Mesero.

### E. Auditoría Trazabilidad del Administrador
1. **Trazabilidad en `/administrador/local/<id>/`**:
   - Consulta el `PuntoVenta` real desde SQLite (`PuntoVenta.objects.all()`).
   - Unifica las ventas reales persistidas por Mesero en SQLite con los tickets demo de `mock_metricas`.
   - Muestra el rol real del creador (`Mesero` con badge verde para comandas persistidas en BD).
   - Filtros de interfaz en cliente permiten buscar por hora, estado y rol sin errores.

### F. Auditoría de Seguridad y Repositorio
1. **Archivos Rastreados**:
   - `.gitignore` protege adecuadamente `importar/`, `version 29 ante de retroalimentar/`, `*.zip`, `__pycache__/` y logs.
   - **Riesgo 1**: `db.sqlite3` se encuentra actualmente bajo seguimiento en Git (`git status` reporta modificaciones directas). Requiere desvincularse del índice.
   - **Riesgo 2**: `SECRET_KEY` está hardcodeada en `Venta_safari/settings.py` con `DEBUG = True`. No se modificó para no romper la compatibilidad local, pero queda registrado como deuda de seguridad.
   - La carpeta de la versión histórica del 29-Sep y el comprimido de distribución están totalmente aislados fuera del scope de Django.

### G. Validación de Pruebas
- `python manage.py check`: 0 incidencias (código limpio).
- `python manage.py test ventas`: **20 de 20 pruebas aprobadas (100% OK en 63.957s)**.

---

### H. MAPA DE CONVERGENCIA 06-OCT

```
========================================================================================
                          MAPA DE CONVERGENCIA 06-OCT (PARQUE SAFARI)
========================================================================================

1. IMPLEMENTADO Y VALIDADO
----------------------------------------------------------------------------------------
- Autenticación real Django, login/logout y decorador de protección @requiere_rol (RF01).
- Apertura de Jornada Operativa con validación estricta de fecha local de hoy (RF02).
- Apertura de Caja individual por cajero con fondo inicial opcional ($0) y restricción UniqueConstraint (RF03).
- Aislamiento estricto de los 3 roles y expulsión en tiempo real de colaboradores desactivados.
- Preservación de contraseña existente en edición de colaboradores y modales SweetAlert2 nativos.
- CRUD completo de Puntos de Venta (Crear, Modificar, Desactivar/Eliminar con soft-delete por ProtectedError).
- Migración estructural '0004_puntoventa_color_puntoventa_icono.py' consolidada en SQLite.
- Formateo monetario global en Pesos Chilenos (CLP) sin abreviaturas (sin "1k" ni "1M") vía templatetag.
- Persistencia atómica de comandas de Mesero en SQLite (Venta, DetalleVenta, Pedido, DetallePedido, Ticket).
- Separación física e independiente de Tickets por destino operativo: COM-COC-XXXX y COM-BAR-XXXX.
- Notas 100% libres en productos de preparación (comida/bebida) con atajo Enter, botón ergonómico
  (.btn-nota-plato, .btn-nota-cajero), feedback visual (.tiene-nota) y visualización destacada en tickets.
- Adaptación táctil para celulares en terminal de Mesero (< 768px): carrusel horizontal de mesas,
  pestañas táctiles de categoría y barra flotante inferior reactiva (.mobile-comanda-bar).
- Centro de Alertas interactivo en cabecera de Administrador con campana reactiva y descarte AJAX.
- Suite oficial de 20 pruebas automatizadas en 'ventas/tests.py' aprobada al 100% (20/20 OK).

2. IMPLEMENTADO PERO REQUIERE CORRECCIÓN
----------------------------------------------------------------------------------------
- 'administrador_local': Lee ventas reales de BD, pero en get_locales_data() aún concatena tickets mock
  demo para los locales 1, 2 y 3.
- Extracción de notas en monitor de Administrador: En get_locales_data(), los tickets reales aún no extraen
  el texto de DetallePedido.observaciones hacia el array JSON de visualización.
- Terminal de Mesero: Permite cambiar de local mediante '?local_id=' en la URL en vez de aislar
  estrictamente al mesero a su 'perfil.punto_venta_actual'.

3. TODAVÍA MOCK / HARDCODEADO
----------------------------------------------------------------------------------------
- Vendedor / Cajero: Emisión de tickets en cobro rápido almacena en 'localStorage' (safari_tickets_desarrollo)
  en vez de persistir en Venta/DetalleVenta/Ticket de SQLite.
- Dashboard analítico ('administrador_dashboard'): Array de 15 meses histórico hardcodeado en la vista.
- Desglose de KPIs en 'get_locales_data()': Categorías y métodos de pago de locales 1, 2 y 3 son simulados.
- Catálogo de productos: Definido en arrays estáticos en vistas/plantillas en lugar de consultar la
  tabla Producto de la BD (pendiente formal de RF05).

4. ADELANTADO RESPECTO AL PLAN CON AUTORIZACIÓN DEL USUARIO
----------------------------------------------------------------------------------------
- CRUD completo de Locales Gastronómicos desde el panel de Administrador.
- Formato monetario global en CLP sin abreviaciones.
- Persistencia de comandas de Mesero a SQLite con trazabilidad en vivo para Administrador.
- Separación física de tickets Cocina/Barra en base de datos.
- Sistema de notas libres de preparación y adaptación móvil ergonómica para celulares de meseros.
- Publicación en GitHub (repositorio público) y paquete de distribución listo en 'importar/'.
- Reconstrucción histórica funcional del 29 de Septiembre ('version 29 ante de retroalimentar/').

5. RIESGOS DE INTEGRIDAD
----------------------------------------------------------------------------------------
- Asimetría transaccional: Mesero impacta tablas reales de SQLite mientras Cajero impacta 'localStorage'.
- Precios y totales confiados al cliente: En 'enviar_comanda', el precio se toma del JSON del cliente sin
  revalidar contra el precio oficial en tabla Producto de SQLite (requiere RF05).
- Despacho entre locales: Un mesero podría emitir comandas en mesas de otro punto de venta vía URL.

6. RIESGOS DE SEGURIDAD / REPOSITORIO
----------------------------------------------------------------------------------------
- 'db.sqlite3' versionado en Git: Riesgo de sobreescritura de datos locales entre clones.
- 'SECRET_KEY' fija y 'DEBUG = True' en 'settings.py': Requiere migrar a variables de entorno para producción.

7. PRUEBAS FALTANTES
----------------------------------------------------------------------------------------
- Prueba automatizada de notas libres: Verificar que 'DetallePedido.observaciones' almacene la nota enviada.
- Prueba de validación de precios del servidor en comanda de mesero.
- Pruebas automatizadas para la persistencia real del Cajero (cuando se migre de localStorage a SQLite).
- Prueba de restricción de mesero a su local asignado.

9. REGLA FUNCIONAL PENDIENTE — MESA / CUENTA ABIERTA
----------------------------------------------------------------------------------------
- Una mesa puede realizar múltiples rondas de pedidos dentro de una misma atención.
- La primera comanda no cierra la Venta.
- Las rondas siguientes deben reutilizar la misma Venta abierta de la Mesa.
- Cada ronda genera únicamente sus nuevos DetallePedido/Tickets.
- La cuenta final acumula todas las rondas.
- La Mesa se libera solo al cerrar/pagar la cuenta.
- Debe impedirse más de una Venta abierta simultánea para la misma Mesa.

8. SIGUIENTE PASO RECOMENDADO
----------------------------------------------------------------------------------------
1. Sincronizar lectura de 'DetallePedido.observaciones' en 'get_locales_data()' para reflejar las notas
   en el modal de detalle del Administrador.
2. Unificar persistencia del Cajero a SQLite reutilizando la lógica atómica de Mesero (eliminando localStorage).
3. Avanzar formalmente a RF05: Catálogo Centralizado de Productos y Menús en SQLite.
========================================================================================
```

## 10. siguiente tarea
- estado actual: **RF05 COMPLETADO (93/93 suite reportada al cierre de RF05)**.
- próxima acción: **ETAPA 0 + RF07** del Plan Maestro.
- orden exacto:
  1. ejecutar línea base (`check`, suite, migraciones, roles);
  2. auditar `Producto`, `PrecioEspecial`, `DetalleVenta`, `Venta` y flujo de precios en Cajero/Mesero;
  3. documentar qué ya existe;
  4. implementar RF07 de forma mínima y segura;
  5. agregar pruebas RF07;
  6. ejecutar suite completa;
  7. verificar regresión manual;
  8. actualizar `AI_CONTEXT.md` con resultados exactos;
  9. detener.
- no iniciar RF08 todavía.
## 11. historial breve
- fecha: 2026-10-31
  - resumen: **RF05 — Reasignación de Mesas y Trazabilidad Operativa de Cuentas Abiertas (Completado al 100%)**:
    * Auditoría previa de modelos `Venta`, `Mesa`, `Pedido`, `Ticket` y ciclo de vida de cuentas abiertas.
    * Creación de modelo de auditoría `ReasignacionMesa` (migración `0012_reasignacionmesa.py`) y registro en Django Admin.
    * Controlador transaccional en `ventas/views.py` bajo acción `reasignar_mesa` con `transaction.atomic()` y bloqueo de concurrencia `select_for_update()`.
    * Blindaje ante escenarios fallidos: rechazo de destino ocupado, inactivo, inexistente, origen sin venta, misma mesa, locales cruzados y doble envío.
    * Interfaz ergonómica en `ventas/templates/ventas/mesero.html` con modal `modalReasignarMesa` y botones directos.
    * Integración de eventos de traslado en el historial del Administrador (`administrador_historial`).
    * Suite ampliada con `SafariRF05ReasignacionMesasTests` (9 pruebas nuevas). Total de la suite general elevado a **93 pruebas automatizadas aprobadas al 100% (Ran 93 tests OK)**.
- fecha: 2026-10-31
  - resumen: **Cambio Forzoso de Contraseña en Primer Ingreso y Checklist Dinámico en Tiempo Real (ISO/IEC 27400)**:
    * Atributo `debe_cambiar_clave` en `PerfilEmpleado` (migración `0011_perfilempleado_debe_cambiar_clave.py`) para obligar a cuentas recién creadas o con clave demo a configurar su contraseña personal al primer ingreso.
    * Intercepción en `login_view`: si el empleado tiene `debe_cambiar_clave = True` o clave expirada (>180 días), se bloquea el acceso al panel operativo y se redirige a `/cambiar-clave-expirada/`.
    * Checklist dinámico reactivo en tiempo real por pulsación (`input` event): 5 reglas visuales en tarjetas individuales (8 caracteres, mayúscula, minúscula, número, símbolo) que pasan de gris a verde esmeralda con checkmark e ícono animado conforme el usuario va escribiendo su clave.
    * Medidor de fortaleza interactivo (0 a 100%) con gradiente semántico (rojo, amarillo, verde) y validación en vivo de coincidencia con la confirmación. Botón de guardado deshabilitado hasta cumplir el 100% de requisitos.
    * Suite oficial de pruebas automatizadas actualizada y validada con 84 tests aprobados al 100%.
- fecha: 2026-10-31
  - resumen: **Implementación de Categorías Madres, Centro de Gestión Unificado y Búsqueda Reactiva por Tecleo**:
    * Reloj discreto de cuenta regresiva de sesión (`⏱️ 15:00`) en navbar con renovación automática en caliente ante cualquier interacción física (mouse, teclado, touch, scroll) evitando cierres imprevistos durante el servicio.
    * Rediseño del header de Administrador: eliminación de la saturación de 10 botones horizontales reemplazándolos por 3 Categorías Madres (`Locales`, `Administración`, `Reportes`).
    * Desarrollo del Centro de Gestión Integral (`/administrador/gestion/`) reuniendo Trabajadores, Mesas, Productos y Menús en una sola pantalla con pestañas interactivas y modales directos.
    * Módulo JavaScript `filtro_tiempo_real.js` para filtrado reactivo instantáneo por cada pulsación de tecla (`input`), permitiendo filtrar al instante al escribir cualquier letra.
    * Suite oficial ampliada con `GestionUnificadaYFiltrosTests` aprobada al 100%.
- fecha: 2026-10-27
  - resumen: **Semana 12 (27/10/2026) y Blindaje de Resiliencia completados**:
    * Implementación del proceso principal de ventas: ciclo de jornada (RF02), apertura/cierre de cajas con fondo de sencillo (RF03), ventas en barra vs. comandas de salón.
    * Subproceso de cuadratura y arqueo al cerrar caja: desglose por unidades de billetes ($20.000 a $1.000) y monedas ($500 a $1), con cálculo dinámico de exactitud, sobrante o faltante.
    * Implementación de regla de redondeo en efectivo adaptada de la Ley N° 20.956 (1 a 4 hacia abajo, 5 a 9 hacia arriba).
    * Elaboración de la primera mitad del informe técnico oficial para INACAP: `Evaluacion_3_Ingenieria_de_Software_Parque_Safari.docx` (Sección 1: Diseño Lógico y Sección 2: Diseño Físico).
    * Implementación de las 5 protecciones de seguridad y resiliencia: Control Anti-Fraude de anulaciones con clave de supervisor, concurrencia `select_for_update`, auto-logout por inactividad a los 15 min con advertencia modal, rate limiting de red contra ataques de fuerza bruta y comando de backups en caliente `backup_safari` con GZIP y SHA-256.
- fecha: 2026-09-22
  - resumen: Creación de proyecto Django Venta_safari, app ventas, settings y templates iniciales
- fecha: 2026-09-22
  - resumen: Prototipo inicial de Vendedor con catálogo de productos y totalizador reactivo
- fecha: 2026-09-29
  - resumen: Pantalla intermedia de Vendedor (`/vendedor/`) con monitor de tickets en desarrollo y separación de creación de tickets
- fecha: 2026-09-29
  - resumen: Módulo de Administrador con supervisión de 3 locales, auditoría y dashboard analítico de 15 meses
- fecha: 2026-09-29
  - resumen: Fase 1 backend completada (17 modelos de datos iniciales en `ventas/models.py`, migración `0001_initial.py` y registro en admin)
- fecha: 2026-09-29
  - resumen: Módulo de Gestión de Trabajadores (`/administrador/trabajadores/`) con CRUD, búsqueda dinámica, límite de 1 puesto único y alertas de traslado
- fecha: 2026-09-29
  - resumen: Terminal Dinámico de Meseros (`/mesero/`) con asignación de mesas y despacho de tickets separados por zona (Cocina y Barra)
- fecha: 2026-09-29
  - resumen: Fase 2A Backend completada al 100% (Autenticación real Django, control de acceso por roles con `@requiere_rol`, apertura de jornada RF02 y caja individual RF03 con prevención de duplicados)
- fecha: 2026-09-29
  - resumen: Fase 2A.1 Estabilización funcional + rendimiento completada (Seeding desacoplado a `poblar_safari`, latencia reducida a 5ms, anti doble envío frontend, zona horaria Chile, jornada de fecha actual, caja con fondo opcional, validación estricta de punto de venta, contraseña explícita de trabajadores, `UniqueConstraint` en Caja y suite oficial de tests)
- fecha: 2026-09-30
  - resumen: Auditoría técnica RF04 completada; detección de hardcodeos y falta de CRUD propio de Puntos de Venta.
- fecha: 2026-10-06
  - resumen: Adelantos autorizados consolidados (CRUD completo de `PuntoVenta` con migración `0004`, formato monetario global en Pesos Chilenos sin abreviaturas, trazabilidad en vivo de comandas de mesero con separación Cocina/Barra en SQLite y suite oficial ampliada a 20 pruebas aprobadas al 100%).
- fecha: 2026-10-06
  - resumen: Implementación de **Notas Libres en Productos de Preparación** para Mesero y Cajero (eliminación de filtros rígidos, atajo Enter, botones táctiles ergonómicos `.btn-nota-plato` y `.btn-nota-cajero`, badge `.tiene-nota` y visualización roja destacada en comandas y tickets térmicos).
- fecha: 2026-10-06
  - resumen: **Adaptación Smartphone para Meseros** (`< 768px`) con carrusel horizontal táctil de mesas, categorías con scroll horizontal y barra flotante inferior reactiva (`.mobile-comanda-bar`).
- fecha: 2026-10-06
  - resumen: **Auditoría de Convergencia Post-Movimiento y Mapa de Convergencia 06-Oct** completados e incorporados formalmente en `AI_CONTEXT.md` para revisión y coordinación con ChatGPT.

- fecha: 2026-10-06
  - resumen: Se incorpora regla operativa de Mesa/Cuenta Abierta: una mesa puede generar múltiples pedidos/comandas durante la misma atención; todas las rondas pertenecen a una única Venta abierta y la mesa se libera únicamente cuando el cliente solicita la cuenta y se completa el cierre/pago.

## 12. reglas permanentes
- desde este punto, Antigravity debe seguir el Plan Maestro RF07–RF18 registrado en este archivo, un RF a la vez y sin saltarse auditoría, escenarios de falla, pruebas, regresión y revisión
- prioridad funcional oficial: RF01–RF18; Requerimientos Futuros 19–24 continúan totalmente excluidos
- módulos de huéspedes/cabañas/desayuno/ofertas quedan congelados y no deben desplazar el trabajo de RF01–RF18
- cada RF restante debe implementarse de forma incremental, con auditoría previa, escenarios de error, pruebas y revisión antes del siguiente RF

- para la preparación de Semana 11, el último conteo vigente reportado es 41/41 pruebas después del CRUD de Mesas; cifras menores que aparezcan en bloques anteriores se consideran históricas
- prioridad académica inmediata: recuperar completamente los objetivos de Semana 10 (13/10/2026) y llegar a la clase de Semana 11 (20/10/2026) con CRUD de Usuarios y PuntoVenta consolidados, CRUD básico de Mesas implementado y avance inicial real de Productos/Menús
- desde la retroalimentación de Informe 2 y su implementación posterior, `COCINERO` es un rol operativo vigente del sistema junto a `ADMINISTRADOR`, `CAJERO` y `MESERO`; no eliminarlo sin nueva instrucción del usuario/docente
- si el usuario autoriza directamente un adelanto funcional para una presentación o demostración, registrarlo como adelanto autorizado y no tratarlo como desviación; posteriormente auditar su integración con los RF vigentes
- leer este archivo antes de cambios importantes
- actualizarlo después de cambios relevantes
- no inventar información
- mantenerlo breve
- registrar errores exactos
- registrar soluciones intentadas
- no modificar requisitos sin autorización
- preparar dudas para ChatGPT solo cuando sea necesario

## 13. protocolo de trabajo ChatGPT ↔ Antigravity
- objetivo: Usar este archivo como canal único de contexto y coordinación técnica para el desarrollo del Proyecto Integrado.
- rol de ChatGPT: Revisar el estado informado en este archivo, contrastarlo con los requerimientos vigentes del Proyecto Integrado y proponer la siguiente orden técnica.
- rol de Antigravity: Ejecutar en el proyecto local las órdenes técnicas registradas en este archivo y luego actualizar el estado, cambios, errores y dudas.

