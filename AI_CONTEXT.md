# AI_CONTEXT

## 1. proyecto
- nombre: Venta_safari
- tipo de proyecto: Web (Django)
- tecnologías principales: Python 3.14.6, Django 6.1, Bootstrap 5.3, Bootstrap Icons 1.11, JavaScript (Vanilla), CSS3 modular, SQLite

## 2. objetivo actual
- tarea actual: **Estandarización de Tickets Térmicos de Cocina y Barra a 80mm (8 cm) Monocromático Blanco y Negro sin Emojis según Pauta del Docente (100% OK)**.
- resultado esperado: Los tickets de comanda para Cocina y Barra se ajustan con fidelidad absoluta a la boleta real de Parque Safari (`SAFARI ADVENTURE SAC`, `RUT: 76.041.631-2`) entregada por el docente: diseño 100% monocromático blanco y negro, ancho estricto de 80mm (8 cm), corte dentado (sawtooth), tipografía monoespaciada Courier, notas de preparación en texto plano `* NOTA: <INSTRUCCION>`, sin ningún tipo de emoji (evitando manchas o caracteres corruptos en hardware térmico ESC/POS) y soporte de impresión directa vía `@media print` con botón de impresión rápida.

## 3. estado actual
- estado: Servidor de desarrollo activo en http://127.0.0.1:8000/. Código limpio con 0 incidencias (`manage.py check`) y suite de **23 pruebas automatizadas oficiales (`ventas/tests.py`) aprobadas al 100% (23/23 OK)**.
- último avance: **Estandarización de Tickets Térmicos de Producción para Cocina y Barra (80mm B&W)**:
  - **Membrete Legal Idéntico al Voucher del Docente**:
    - Empresa: `SAFARI ADVENTURE` / `SAFARI ADVENTURE SAC`
    - Identificación Tributaria: `RUT: 76.041.631-2`
    - Dirección legal: `CAMINO PUNTA DE CORTEZ N° 4220 PARCELA N° 38, LOTE B (RUTA H-30) RANCAGUA LIBERTADOR BERNARDO O'HIGGINS`
    - Lugar de expedición dinámico: `{{ local_actual.nombre|upper }}`
  - **Erradicación Total de Emojis en Impresión Térmica**:
    - Retiro de emojis (`🔥`, `🍹`, `👉`) en títulos, badges, líneas de ítems y notas de comandas.
    - Notas formateadas de manera estándar para comandera física: `* NOTA: <TEXTO EN MAYÚSCULAS>` (ej. `* NOTA: SIN QUESO CHEDDAR`).
    - Limpieza homogénea aplicada en `mesero.html`, `vendedor.html` y `vendedor_crear_ticket.html`.
  - **Formato Físico 8 cm (80mm) y Tipografía Monocromo**:
    - Dimensiones acotadas a `width: 80mm; max-width: 320px;` en pantalla y `80mm` en papel.
    - Tipografía monoespaciada `Courier New, monospace`, tinta negra pura `#000000` sobre papel blanco térmico `#ffffff`.
    - Separadores estandarizados tipo ESC/POS (`================================================` y `------------------------------------------------`).
    - Simulación de corte dentado superior e inferior (*sawtooth pattern*).
  - **Soporte de Impresión Directa ESC/POS (`@media print`)**:
    - Regla de impresión configurada para aislar la comanda térmica a 80mm continuo por tickets sin márgenes ni encabezados de navegador.
    - Botón "Imprimir Comandas (80mm)" integrado en el modal `#modalTickets`.
  - **Validación Automatizada**: Las 23 pruebas de Django continúan pasando al 100% (`Ran 23 tests - OK`).
- avances previos:
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
- rendimiento crítico anterior: **RESUELTO**.
- `python manage.py check`: 0 incidencias reportadas (0 silenced).
- suite oficial de pruebas: **23 de 23 pruebas automatizadas aprobadas** (`Ran 23 tests in 86.290s - OK`). Documentación reconciliada al 100%.
- observaciones críticas de ChatGPT atendidas en auditoría:
  1. **Avances adelantados autorizados por el usuario**: Reconocidos y formalmente auditados en la sección 9 (CRUD de `PuntoVenta`, CLP global, trazabilidad de tickets, notas libres de preparación, adaptación móvil, repositorio GitHub y paquete importable).
  2. **Documentación contradictoria**: Reconciliada en su totalidad; se eliminaron las referencias desactualizadas a 15 pruebas y a la inexistencia de CRUD.
  3. **Persistencia de pedidos y comanda de Mesero**: Confirmado que persiste de forma atómica en SQLite: `Venta`, `DetalleVenta`, `Pedido`, `DetallePedido` (incluyendo observaciones/notas de preparación) y `Ticket` (con separación física por destino Cocina/Barra).
  4. **Asimetría Mesero vs Cajero**: Formalmente documentada. Mesero persiste en SQLite; Cajero abre jornada/caja en SQLite pero mantiene la simulación de cobro y tickets en `localStorage`.
  5. **Modelo PuntoVenta**: Confirmado que `icono` y `color` son campos reales en `models.py` creados mediante la migración oficial `0004_puntoventa_color_puntoventa_icono.py`.
  6. **Eliminación de locales con protección**: Confirmado que `eliminar_local` captura `models.ProtectedError` aplicando soft-delete (`activo=False`) para resguardar ventas y transacciones históricas.
  7. **Seguridad y repositorio**: Se identificó que `db.sqlite3` está bajo seguimiento de Git y `SECRET_KEY` hardcodeada en `settings.py`; documentados como riesgos para su próxima parametrización.
  8. **Versión histórica del 29-Sep y paquete de importación**: Completamente aislados del ciclo de ejecución de Django, excluidos por `.gitignore` y sin interferencia con la suite de pruebas.

## 7. dudas para ChatGPT
- aclaración funcional nueva del usuario:
  - En atención de mesa, la primera comanda **no debe cerrar la venta ni la mesa**.
  - Una misma mesa puede pedir primero varios productos y después agregar nuevos productos en una o más rondas.
  - Cada ronda nueva debe incorporarse a la misma atención abierta de esa mesa.
  - Los nuevos productos deben generar únicamente sus nuevas comandas/tickets de Cocina o Barra según corresponda.
  - La mesa y la venta permanecen abiertas hasta que el cliente solicite la cuenta.
  - Recién al solicitar la cuenta y completar el cierre/pago se debe cerrar la venta global y liberar la mesa.
- ejemplo operacional:
  - Mesa 5 pide 4 productos -> se crea la atención y se despachan las comandas correspondientes.
  - Más tarde Mesa 5 pide 2 productos adicionales -> se agregan a la misma atención abierta y se generan solo los tickets de esos 2 productos.
  - La cuenta final debe considerar los 6 productos.
  - Solo al cerrar/pagar la cuenta se marca la atención/venta como cerrada y la mesa vuelve a quedar disponible.
- decisión: Esta regla debe considerarse obligatoria antes de consolidar la persistencia definitiva de Mesero/Cajero y antes de cerrar el diseño de RF05/RF11/RF12/RF13.
## 8. respuesta de ChatGPT
- revisión general: La auditoría de convergencia queda aceptada. Se incorpora además una regla operativa nueva y prioritaria: **Mesa/Cuenta Abierta con pedidos incrementales**.
- interpretación funcional aprobada:
  1. La unidad global de la atención en mesa debe ser una `Venta` abierta asociada a una `Mesa`.
  2. Esa `Venta` puede contener **múltiples `Pedido`** a lo largo del tiempo.
  3. Cada vez que el Mesero agrega productos:
     - no se crea una venta independiente si ya existe una venta abierta para esa mesa;
     - se crea una nueva ronda/pedido asociada a la misma venta;
     - se crean sus `DetallePedido`;
     - se generan únicamente los `Ticket` necesarios para los productos nuevos (Cocina/Barra).
  4. Los productos pedidos anteriormente no deben volver a imprimirse cuando se agrega una nueva ronda.
  5. La `Mesa` permanece `OCUPADA` mientras exista una atención/venta abierta.
  6. La cuenta final debe sumar todos los detalles/pedidos vinculados a esa misma venta.
  7. El cierre real ocurre únicamente cuando el cliente solicita la cuenta y se ejecuta la acción de cerrar/pagar.
  8. Al cerrar correctamente:
     - la `Venta` cambia a estado cerrado/finalizado según el modelo vigente;
     - se registra el cierre/pago cuando esa fase sea implementada;
     - la `Mesa` vuelve a estado disponible/libre.
- regla de integridad:
  - No debe existir más de una atención/venta abierta simultánea para la misma mesa y Punto de Venta.
  - Antes de crear una nueva Venta para modalidad `MESA`, el backend debe buscar si ya existe una atención abierta para esa mesa y reutilizarla.
- diferencia con venta rápida:
  - `VENTA_RAPIDA` puede completarse en una sola operación.
  - `MESA` debe soportar múltiples pedidos antes del cierre.
- impacto en el desarrollo actual:
  - La persistencia de Mesero implementada hasta ahora debe auditarse para verificar si actualmente crea una Venta nueva en cada comanda.
  - Si lo hace, **no corregir de forma improvisada todavía**: documentar el comportamiento exacto y adaptar el flujo cuando se ejecute la siguiente fase autorizada.
  - Esta regla debe incorporarse antes de unificar Cajero/Mesero y antes de considerar cerrado el flujo real de ventas de mesa.
- pruebas futuras obligatorias:
  1. Primera comanda en una mesa crea una atención/venta abierta.
  2. Segunda comanda en la misma mesa reutiliza la misma Venta.
  3. Segunda comanda genera únicamente tickets para los productos nuevos.
  4. Total de cuenta acumula correctamente todas las rondas.
  5. Mesa permanece ocupada después de cada comanda intermedia.
  6. Cerrar/pagar libera la mesa.
  7. No se permiten dos ventas abiertas simultáneas para la misma mesa.
- decisión sobre próximos pasos:
  - Antes de mover Cajero a SQLite o cerrar RF05, Antigravity debe registrar si el flujo actual de Mesero ya reutiliza una Venta abierta o crea una nueva por cada `enviar_comanda`.
  - No implementar todavía el cierre/pago si no está definido el flujo de métodos de pago.
- estado de aplicación: regla funcional registrada; implementación completa pendiente de fase autorizada.
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
- próxima acción: **Auditar el comportamiento actual de Mesero respecto de Mesa/Cuenta Abierta**, sin ampliar todavía el sistema.
- prioridad: Alta
- verificar específicamente:
  - si `enviar_comanda` crea una nueva `Venta` en cada pedido o reutiliza una venta abierta de la mesa;
  - cómo se calcula actualmente el total acumulado de la mesa;
  - si una segunda ronda vuelve a imprimir productos anteriores o solo los nuevos;
  - cuándo cambia actualmente el estado de `Mesa`;
  - si existe ya algún estado de `Venta` que permita distinguir ABIERTA/CERRADA o equivalente.
- resultado esperado:
  - documentar el comportamiento real actual;
  - indicar qué modelos/campos existentes pueden reutilizarse;
  - indicar el cambio mínimo necesario para soportar múltiples pedidos por mesa sin perder trazabilidad.
- no implementar todavía:
  - cierre/pago definitivo;
  - métodos de pago;
  - persistencia nueva del Cajero;
  - RF05 completo;
  - refactor masivo.
- al finalizar: devolver `AI_CONTEXT.md` al usuario para revisión de ChatGPT.
## 11. historial breve
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

