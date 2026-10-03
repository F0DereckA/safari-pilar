# AI_CONTEXT

## 1. proyecto
- nombre: Venta_safari
- tipo de proyecto: Web (Django)
- tecnologías principales: Python 3.14.6, Django 6.1, Bootstrap 5.3, Bootstrap Icons 1.11, JavaScript (Vanilla), CSS3 modular, SQLite

## 2. objetivo actual
- tarea actual: **RF04.1 — Aislamiento operativo por Punto de Venta para Mesero y corrección de fallbacks arbitrarios**.
- resultado esperado: Corregir únicamente las inconsistencias operativas detectadas en la auditoría RF04 sin construir todavía el CRUD de Puntos de Venta ni modificar catálogo, ventas o dashboard.
## 3. estado actual
- estado: Sesión finalizada/detenida a petición del usuario. Todas las tareas solicitadas completadas con éxito. Código limpio con 0 incidencias (`manage.py check`) y suite de 15 pruebas automatizadas oficiales (`ventas/tests.py`) aprobadas al 100% (15/15 OK). Servidor de desarrollo detenido limpiamente.
- último avance UX (Panel Administrador): Despeje visual de `/administrador/` eliminando el banner redundante "Supervisión de Locales y Personal" (cuyos accesos ya existen en el header) y conversión del Centro de Alertas en un ícono notificador de campana en la barra superior con badge de conteo en vivo y menú desplegable para consultar las reasignaciones.
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
  - El seeding/hashing fue retirado de las vistas HTTP y movido al comando `poblar_safari`.
  - Latencias locales reportadas después de la corrección: `/administrador/` 5.5 ms, `/vendedor/` 6.1 ms y `/mesero/` 5.0 ms.
  - `python manage.py check`: 0 incidencias.
  - `python manage.py test ventas`: 15 pruebas aprobadas al 100%.
- observaciones de la auditoría Fase 2A.2:
  1. Conteo normalizado y verificado: exactamente **15 pruebas oficiales** ejecutadas y aprobadas en `ventas/tests.py`.
  2. Mejoras UX validadas: SweetAlert2 con estilos Bootstrap 5 y peticiones AJAX en alternancia de estado funcionan armónicamente sin alertas nativas y sin colisionar con `anti_doble_envio.js`.
  3. Trabajador inactivo bloqueado al iniciar sesión y expulsado inmediatamente de sesiones abiertas vía `@requiere_rol`.
  4. Preservación de contraseña validada: la edición de colaboradores sin nueva password conserva el hash intacto.
  5. Limpieza de código completada: `asegurar_locales_y_personal_bd()` fue retirada por completo.

## 7. dudas para ChatGPT
- decisión: **Fase 2A.2 completada al 100%**. Base auditada, estable y con suite de 15 pruebas pasando en verde.
- consulta: ¿Autoriza ChatGPT el inicio formal de la **Fase 2B.1 — Centralización del Catálogo de Alimentos y Bebidas** (modelos de categorías y productos en BD, migración y desacoplamiento de diccionarios hardcodeados en plantillas)?

## 8. respuesta de ChatGPT
- revisión general: Auditoría RF04 aprobada. Se confirma que el modelo `PuntoVenta` y sus relaciones principales ya existen y que el problema inmediato no está en el esquema, sino en varias decisiones de interfaz/lógica que todavía ignoran la asignación real del trabajador.
- decisión de avance: Ejecutar únicamente **RF04.1 — Aislamiento operativo por Punto de Venta**.
- prioridad: Corregir primero consistencia y seguridad operativa. El CRUD de Puntos de Venta y la eliminación de `get_locales_data()` se harán después como pasos separados.

### A. Mesero debe operar únicamente en su Punto de Venta asignado
1. En la vista `/mesero/`, eliminar el fallback `local_defecto = 1`.
2. El `PuntoVenta` activo del mesero debe provenir exclusivamente de `PerfilEmpleado.punto_venta_actual`.
3. Si el mesero no tiene `punto_venta_actual`:
   - no asignar ningún local automáticamente;
   - no mostrar mesas de otro local;
   - bloquear la operación de toma de pedidos;
   - mostrar un mensaje claro indicando que el Administrador debe asignarle un Punto de Venta.
4. Eliminar la capacidad de cambiar de local mediante `?local_id=...` para el Mesero.
5. El selector visual de local debe eliminarse o quedar no operativo si actualmente permite cambiar de local.
6. Las mesas mostradas deben obtenerse únicamente con el `PuntoVenta` real del mesero autenticado.
7. No modificar el modelo `Mesa`; su relación actual con `PuntoVenta` es correcta.

### B. Corregir fallback arbitrario en Gestión de Trabajadores
1. Revisar el flujo `POST (modificar)` de `/administrador/trabajadores/`.
2. Si `nuevo_local` viene vacío:
   - no utilizar `PuntoVenta.objects.first()`;
   - no registrar un destino falso en `AlertaTraslado`.
3. La alerta de traslado debe reflejar únicamente el origen y destino reales.
4. Si el trabajador queda sin Punto de Venta, la lógica debe representar esa desasignación sin inventar otro local.
5. No modificar la regla actual de "máximo un Punto de Venta asignado por trabajador".

### C. Eliminar textos de fallback que oculten errores de asignación
1. En `vendedor.html` y `vendedor_crear_ticket.html`, retirar el fallback visual fijo `"Restaurante Central Safari"` para `punto_venta.nombre`.
2. Si por alguna razón no existe Punto de Venta en el contexto:
   - mostrar un texto neutral como `"Sin punto de venta asignado"`;
   - no aparentar que el Cajero pertenece al Restaurante Central.
3. No modificar la lógica de Caja que ya bloquea correctamente a Cajeros sin Punto de Venta.

### D. Pruebas obligatorias de RF04.1
Agregar pruebas específicas sin eliminar las 15 actuales:
1. Mesero con Punto de Venta asignado ve únicamente las mesas de ese Punto de Venta.
2. Mesero sin Punto de Venta no puede operar el terminal ni recibe fallback al Local 1.
3. `?local_id=` no permite a un Mesero acceder a mesas de otro Punto de Venta.
4. Desasignar un trabajador de un Punto de Venta no genera una `AlertaTraslado` con un destino arbitrario.
5. Cajero sin Punto de Venta continúa bloqueado como en las pruebas existentes.

### E. Límites de esta orden
- No crear CRUD de Puntos de Venta todavía.
- No modificar `get_locales_data()` todavía.
- No cambiar `/administrador/` ni `/administrador/local/<id>/` salvo que sea estrictamente necesario para evitar un error directo provocado por RF04.1.
- No tocar `Producto`, `Categoria`, `Menu` ni catálogo.
- No persistir ventas, pedidos o tickets.
- No modificar dashboard.
- No crear nuevos roles.
- No cambiar el esquema de `PuntoVenta`, `Mesa`, `Caja` o `PerfilEmpleado` salvo que Antigravity detecte un impedimento técnico real; si ocurre, documentarlo antes de hacer una migración.

### F. Validación final
- Ejecutar `python manage.py check`.
- Ejecutar `python manage.py test ventas`.
- Informar el número final exacto de pruebas.
- Verificar manualmente con dos Meseros asignados a Puntos de Venta distintos que cada uno vea exclusivamente sus propias mesas.
- Confirmar que ninguna URL o selector permita cambiar de Punto de Venta desde el terminal de Mesero.
- estado de aplicación: pendiente de ejecución por Antigravity
## 9. orden actual ejecutada — Auditoría Técnica de RF04 (Puntos de Venta y Asignación Operativa)

### 1. Inspección del modelo `PuntoVenta` existente (`ventas/models.py`, líneas 67–82)
- **Campos reales que posee**:
  - `nombre`: `models.CharField(max_length=100, unique=True)`
  - `tipo`: `models.CharField(max_length=50, blank=True, null=True, help_text="Ej: Restaurante, Cafetería, Kiosco")`
  - `descripcion`: `models.TextField(blank=True, null=True)`
  - `activo`: `models.BooleanField(default=True)`
  - `creado_en`: `models.DateTimeField(auto_now_add=True)`
- **Relaciones activas con otros modelos**:
  - `PerfilEmpleado.punto_venta_actual`: `ForeignKey('PuntoVenta', on_delete=models.SET_NULL, null=True, blank=True, related_name='empleados_asignados')`
  - `Caja.punto_venta`: `ForeignKey(PuntoVenta, on_delete=models.PROTECT, related_name='cajas')`
  - `Producto.puntos_venta`: `ManyToManyField(PuntoVenta, blank=True, related_name='productos_disponibles')`
  - `Menu.punto_venta`: `ForeignKey(PuntoVenta, on_delete=models.CASCADE, related_name='menus')`
  - `Mesa.punto_venta`: `ForeignKey(PuntoVenta, on_delete=models.PROTECT, related_name='mesas')` con restricción `unique_together = ('identificador', 'punto_venta')`
  - `Venta.punto_venta`: `ForeignKey(PuntoVenta, on_delete=models.PROTECT, related_name='ventas')`
  - `ConsumoInterno.punto_venta`: `ForeignKey(PuntoVenta, on_delete=models.PROTECT, related_name='consumos_internos')`
  - `AlertaTraslado.punto_venta_origen`: `ForeignKey(PuntoVenta, on_delete=models.SET_NULL, null=True, blank=True, related_name='traslados_salientes')`
  - `AlertaTraslado.punto_venta_destino`: `ForeignKey(PuntoVenta, on_delete=models.CASCADE, related_name='traslados_entrantes')`
- **Nota de diseño**: `Jornada` no se vincula directamente a `PuntoVenta` porque la jornada es única y global del parque; las cajas y ventas sí se asocian de forma individual a su respectivo `PuntoVenta`.

### 2. Revisión de los 3 locales actuales y su creación
- **Origen de creación**: Se crean **única y exclusivamente** mediante el comando de gestión `poblar_safari` (`ventas/management/commands/poblar_safari.py`, líneas 20–58).
- **Inexistencia en migraciones o vistas**: Las migraciones (0001, 0002, 0003) son 100% de esquema estructural DDL; ninguna inserta filas en `PuntoVenta`. En `ventas/views.py` no existe ninguna rutina de creación de locales (la antigua `asegurar_locales_y_personal_bd()` fue retirada en Fase 2A.2).
- **Idempotencia comprobada**: `poblar_safari` implementa `PuntoVenta.objects.get_or_create(id=ldef["id"], defaults={...})`. Si los locales ID 1, 2 y 3 ya existen en SQLite, se omiten sin duplicar registros ni fallar por `IntegrityError`.

### 3. Hardcodeo de locales encontrado
- **En `ventas/views.py`**:
  1. `get_locales_data()` (líneas 12–204): Función que retorna un diccionario Python fijo indexado con claves `{1, 2, 3}` con métricas simuladas de ventas, tickets, recaudación, porcentajes, colores e iconos CSS.
  2. `/administrador/` (`administrador`, líneas 504–530): Invoca `locales = get_locales_data()`. No consulta `PuntoVenta.objects.all()`. Un nuevo local creado en la BD jamás aparecería en este panel general.
  3. `/administrador/local/<id>/` (`administrador_local`, líneas 534–552): Consulta `if local_id not in locales: raise Http404(...)`. Si se intenta abrir un local con ID 4 (creado en BD), arroja 404 de inmediato.
  4. `/administrador/trabajadores/` (`administrador_trabajadores`, línea 629): En `POST (modificar)`, si `nuevo_local` queda vacío en el formulario, asigna arbitrariamente `punto_venta_destino=PuntoVenta.objects.first()`. (En el `GET`, sí consulta dinámicamente `PuntoVenta.objects.filter(activo=True)`).
  5. `/vendedor/` (`vendedor`): No hardcodea lista de locales; toma `punto_venta = perfil.punto_venta_actual`.
  6. `/mesero/` (`mesero`, líneas 796 y 800–805): Si el mesero logueado no tiene local asignado, fija `local_defecto = 1`. Además, permite cambiar de local mediante el parámetro de consulta `?local_id=...`, permitiendo a un mesero atender mesas de cualquier local.
- **En Plantillas HTML**:
  1. `vendedor.html` (línea 46): `<small class="text-muted">{{ punto_venta.nombre|default:"Restaurante Central Safari" }}</small>` (texto de respaldo fijo).
  2. `vendedor_crear_ticket.html` (línea 46): `<small class="text-muted">{{ punto_venta.nombre|default:"Restaurante Central Safari" }}</small>` (texto de respaldo fijo).
  3. `administrador.html` (líneas 94, 150, 203): Textos estáticos en el DOM: *"los 3 locales"*, *"Consolidado 3 Locales (CLP)"*, *"ESTADO OPERATIVO DE LOS 3 LOCALES GASTRONÓMICOS"*.
  4. `administrador_local.html` (línea 64): Texto estático *"Selector Rápido entre los 3 Locales"*.
  5. `index.html` (línea 261): Tarjeta demo con etiqueta fija `"Restaurante #1"`.
- **En JavaScript**:
  - `mesero.html` y `vendedor_crear_ticket.html` gestionan tickets en `localStorage` con estructuras mock en el navegador que no integran el `punto_venta_id` dinámico de la base de datos.

### 4. Asignación operativa de trabajadores por rol
- **Mecanismo**: `PerfilEmpleado.punto_venta_actual` implementa el principio de **Puesto Único de Trabajo** (1 colaborador = máximo 1 local asignado a la vez). Al reasignar un trabajador en `/administrador/trabajadores/`, el sistema registra una `AlertaTraslado`.
- **Comportamiento actual verificado por rol**:
  - **Cajero (`CAJERO`)**: Requiere obligatoriamente un `PuntoVenta` asignado.
    - Si no tiene local asignado: los botones de apertura de jornada y caja se muestran bloqueados (`disabled`) con aviso en pantalla. Si envía el formulario, la vista lo rechaza con mensaje de error (`test_cajero_sin_punto_venta_bloqueado`).
  - **Mesero (`MESERO`)**: Debería estar asignado a un local, pero la vista `/mesero/` no lo exige de forma restrictiva:
    - Si no tiene `punto_venta_actual`, el sistema aplica fallback al Local 1 (`local_defecto = 1`).
    - El mesero puede conmutar entre locales mediante el selector visual (`?local_id=`), operando sobre mesas que no corresponden a su puesto de trabajo asignado.
  - **Administrador (`ADMINISTRADOR`)**: No requiere `PuntoVenta` asignado. Tiene acceso global a todos los módulos y locales del parque.

### 5. Revisión de Mesas y terminal de Mesero
- **Asociación en Base de Datos**: Sí, cada `Mesa` está asociada a un `PuntoVenta` vía `models.ForeignKey(PuntoVenta, on_delete=models.PROTECT, related_name='mesas')`. Existen 14 mesas reales creadas por `poblar_safari` (8 en Local 1, 4 en Local 2, 2 en Local 3).
- **Comportamiento en terminal de Mesero**:
  - Las mesas sí se consultan desde SQLite mediante `Mesa.objects.filter(punto_venta=local_actual)`.
  - **Inconsistencia detectada**: `local_actual` no está anclado obligatoriamente al `punto_venta_actual` del mesero, permitiendo manipular mesas de cualquier local mediante el parámetro URL o el dropdown.

### 6. Revisión de Caja
- **Derivación**: `Caja.punto_venta` deriva directa y exclusivamente de `perfil.punto_venta_actual` del cajero tanto en `abrir_jornada` como en `abrir_caja`.
- **Inexistencia de fallback arbitrario**: Confirmado. Si el cajero no tiene punto de venta asignado, la creación de caja se aborta inmediatamente sin recurrir a `PuntoVenta.objects.first()`.

### 7. Revisión de interfaz administrativa
- **Estado de gestión de Puntos de Venta**: Actualmente **no existe un CRUD de Puntos de Venta** en el frontend de la aplicación.
  - Solo existe visualización estática en `/administrador/` y `/administrador/local/<id>/` alimentada por el diccionario mock `get_locales_data()`.
  - La creación, edición o desactivación de locales físicos actualmente solo es posible a través del Django Admin nativo (`/admin/`).

### 8. Mapa de estado RF04

| Categoría | Detalle y Estado Técnico |
| :--- | :--- |
| **RF04 ya implementado** | • Modelo `PuntoVenta` en SQLite con campos y restricciones.<br>• Relaciones FK en `PerfilEmpleado`, `Caja`, `Mesa`, `Menu`, `Producto`, `Venta`.<br>• Asignación de puesto único a trabajadores con alertas automáticas (`AlertaTraslado`).<br>• Bloqueo estricto de apertura de caja para cajeros sin local.<br>• Idempotencia en población de locales vía `poblar_safari`. |
| **RF04 parcialmente implementado** | • Vista de Mesero (`/mesero/`): consulta mesas reales de la BD, pero permite cambiar de local libremente ignorando el puesto asignado.<br>• Selectores de local en CRUD de trabajadores: lee locales de la BD, pero ante desasignación genera fallback a `PuntoVenta.objects.first()` en alertas. |
| **RF04 faltante** | • Interfaz administrativa para Gestión de Puntos de Venta (CRUD para crear, editar, activar/desactivar locales).<br>• Desacoplamiento de `get_locales_data()`: paneles de `/administrador/` deben leer locales y métricas desde la BD.<br>• Aislamiento estricto del mesero a su local asignado (o definición explícita de política de mesero rotativo). |
| **Hardcodeos encontrados** | • Diccionario `get_locales_data()` en `ventas/views.py` (IDs 1, 2, 3 con métricas mock).<br>• Lógica 404 en `administrador_local` si `local_id not in [1, 2, 3]`.<br>• Fallback `default:"Restaurante Central Safari"` en `vendedor.html` y `vendedor_crear_ticket.html`.<br>• Textos estáticos *"los 3 locales"* en plantillas de administrador.<br>• Fallback `local_defecto = 1` en terminal de meseros. |
| **Archivos involucrados** | • `ventas/models.py`<br>• `ventas/views.py`<br>• `ventas/management/commands/poblar_safari.py`<br>• `ventas/templates/ventas/administrador.html`<br>• `ventas/templates/ventas/administrador_local.html`<br>• `ventas/templates/ventas/administrador_trabajadores.html`<br>• `ventas/templates/ventas/vendedor.html`<br>• `ventas/templates/ventas/vendedor_crear_ticket.html`<br>• `ventas/templates/ventas/mesero.html` |
| **Riesgos antes de RF05** | 1. Si se asocian menús o productos a `PuntoVenta` antes de limpiar el mock de `get_locales_data()`, el administrador seguirá viendo datos estáticos desalineados de la BD.<br>2. Si se crean productos por local sin corregir el selector de mesero, un mesero podría vender productos en mesas de otro punto de venta. |

- validación técnica:
  - `python manage.py check`: 0 incidencias.
  - 15/15 pruebas automatizadas vigentes y aprobadas (`Ran 15 tests in 50.377s - OK`).
  - Cero modificaciones a modelos, migraciones o lógica operativa en esta orden de auditoría.

## 10. siguiente tarea
- próxima acción: Ejecutar exclusivamente **RF04.1 — Aislamiento operativo por Punto de Venta** definido en la sección 8.
- prioridad: Alta
- objetivo inmediato: Dejar a Cajero y Mesero completamente ligados a su `punto_venta_actual` real y eliminar fallbacks que puedan hacerlos operar sobre otro local.
- no iniciar todavía:
  - CRUD de Puntos de Venta;
  - reemplazo de `get_locales_data()`;
  - RF05;
  - catálogo en SQLite;
  - persistencia de ventas/pedidos/tickets;
  - dashboard real.
- después de completar RF04.1: Devolver `AI_CONTEXT.md` al usuario. El siguiente paso previsto será RF04.2, centrado en eliminar el hardcodeo del panel Administrador y hacer que lea los Puntos de Venta reales desde SQLite.
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
  - resumen: Fase 2A.1 Estabilización funcional + rendimiento completada (Seeding desacoplado a `poblar_safari`, latencia reducida a 5ms, anti doble envío frontend, zona horaria Chile, jornada de fecha actual, caja con fondo opcional, validación estricta de punto de venta, contraseña explícita de trabajadores, `UniqueConstraint` en Caja y suite oficial de 11 tests en `ventas/tests.py` aprobada al 100%)

- fecha: 2026-09-30
  - resumen: Auditoría técnica RF04 completada; se detectaron hardcodeos en panel Administrador, fallback de Mesero al Local 1, cambio libre de local mediante `?local_id=`, fallback arbitrario en alertas de traslado y ausencia de CRUD propio de Puntos de Venta.

## 12. reglas permanentes
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
