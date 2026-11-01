# AI_CONTEXT

## 1. PROYECTO
- **nombre:** Venta_safari
- **tipo:** Web (Django)
- **stack actual:** Python 3.14.6, Django 6.1, Bootstrap 5.3, Bootstrap Icons 1.11, JavaScript (Vanilla), CSS3 modular, SQLite (entorno activo local) / PostgreSQL (soporte formal configurado en `.env` para despliegue).

---

## 2. ESTADO VIGENTE ÚNICO
- RF01–RF18: **COMPLETADOS AL 100%**.
- Suite oficial: **220/220 pruebas aprobadas**.
- `python manage.py check`: **0 incidencias**.
- Migraciones `ventas`: **20 aplicadas**.
- Motor activo actual: **SQLite**.
- Modelos Django explícitos en `ventas`: **25**.
- Tablas físicas propias de `ventas`: **27** (25 directas de modelos + 2 tablas intermedias ManyToMany automáticas).
- Tablas Django del framework: **10** (`auth_*`, `django_*`).
- Total de tablas físicas en SQLite: **37**.
- Roles oficiales:
  - `ADMINISTRADOR`
  - `CAJERO`
  - `MESERO`
  - `COCINERO`
- Mocks evaluables: **0%**.
- `.env`: protegido y fuera de Git.
- `db.sqlite3`: fuera del índice Git y preservado localmente.
- Benchmark vigente:
  - 20 usuarios concurrentes;
  - 100 peticiones;
  - 100% éxito;
  - 166.59 RPS;
  - 70.84 ms promedio;
  - P95 524.29 ms.
- Bloqueantes funcionales conocidos: **NINGUNO**.
- Desarrollo funcional: **STOP TOTAL**.
- Siguiente tarea de desarrollo: **NINGUNA**.
- Fase documental: pendiente únicamente cuando el usuario la autorice.
- Recordatorios académicos: conservados, **NO prioridad actual**.

---

## 3. ALCANCE OFICIAL
- **RF01–RF18:** Incluidos y cerrados al 100% con persistencia real y pruebas automatizadas.
- **RF19–RF24:** Totalmente excluidos del alcance oficial.
- **Módulos extras:** Huéspedes, cabañas, desayuno y ofertas permanecen congelados y fuera del núcleo evaluable.

---

## 4. RESUMEN RF01–RF18

| Requerimiento | Nombre Oficial | Estado | Evidencia Técnica Principal | Cierre Suite |
| :--- | :--- | :---: | :--- | :---: |
| **RF01** | Gestión de Usuarios y Roles | **CERRADO** | Login por perfil, aislamiento RBAC de los 4 roles, cambio obligatorio de clave conforme a políticas internas de seguridad del proyecto | OK |
| **RF02** | Apertura y Cierre de Jornada | **CERRADO** | Jornada operativa con validación de fecha local de hoy y bloqueo de días anteriores | OK |
| **RF03** | Apertura y Arqueo de Caja | **CERRADO** | Caja individual por cajero, fondo inicial opcional ($0) y arqueo en efectivo por denominación | OK |
| **RF04** | Gestión de Mesas por Local | **CERRADO** | CRUD de mesas por Punto de Venta con estados Libre, Ocupada e Inactiva | OK |
| **RF05** | Reasignación de Mesas | **CERRADO** | Traslado transaccional de venta entre mesas sin duplicación de comandas ni tickets | OK (93/93) |
| **RF06** | Registro de Ventas y Cobro POS | **CERRADO** | Registro de ventas, cálculo de IVA y regla de redondeo oficial Ley N° 20.956 | OK |
| **RF07** | Precios Especiales y Convenios | **CERRADO** | Aplicación de convenios y beneficios autorizados durante la venta con trazabilidad en auditoría | OK (107/107) |
| **RF08** | Generación de Tickets con Código Único| **CERRADO** | Tickets térmicos digitales con código único, QR, desglose CLP y control de reimpresiones | OK (116/116) |
| **RF09** | Gestión de Impresión Descentralizada | **CERRADO** | Enrutamiento automático a puntos de impresión (KDS Cocina y KDS Barra) con log de emisión | OK (127/127) |
| **RF10** | Consumo Interno / Fiado del Personal| **CERRADO** | Registro de consumos a colaboradores con saldo acumulado, historial y liquidación por planilla | OK (137/137) |
| **RF11** | Asignación de Mesa o Venta Rápida | **CERRADO** | Modalidad MESA o VENTA_RAPIDA, con alias operativos de mostrador/retiro cuando corresponda | OK (145/145) |
| **RF12** | Comentarios Asociados a Productos | **CERRADO** | Notas libres de preparación reflejadas en comandas y tickets de cocina/barra | OK (153/153) |
| **RF13** | Registro de Entrega de Productos | **CERRADO** | Registro trazable de entrega de pedidos/productos, usuario responsable, ticket asociado y hora exacta | OK (161/161) |
| **RF14** | Gestión de Puntos de Venta (Locales)| **CERRADO** | CRUD de locales gastronómicos, métricas individuales por punto de venta y alertas de traslado | OK (172/172) |
| **RF15** | Posicionamiento de Menús por Local | **CERRADO** | Productos y menús diferenciados por Punto de Venta, con disponibilidad gobernada por BD | OK (185/185) |
| **RF16** | Control de Tiempos de Atención | **CERRADO** | Medición de tiempos de espera, cola y preparación culinaria en KDS | OK (197/197) |
| **RF17** | Gestión de Ocupación de Mesas | **CERRADO** | Monitoreo en vivo de ocupación de mesas, cronómetro comensal y tasa de rotación | OK (207/207) |
| **RF18** | Reportes y Estadísticas Reales | **CERRADO** | Dashboard con 0% mocks, filtros por fecha/local, Top 10 y exportación Word/Excel | OK (220/220) |

---

## 5. MODELO DE DATOS VIGENTE
El modelo de persistencia cuenta exactamente con **25 modelos Django explícitos** en la app `ventas`, los cuales se materializan en **27 tablas físicas propias** en la base de datos SQLite (25 tablas directas de modelos más 2 tablas intermedias generadas automáticamente para relaciones ManyToMany):

| # | Modelo Django | Tabla Física en BD | PK | Claves Foráneas (FK) | Restricciones / Relaciones |
| :---: | :--- | :--- | :---: | :--- | :--- |
| 1 | `PerfilEmpleado` | `ventas_perfilempleado` | `id` | `punto_venta_actual -> PuntoVenta` | `OneToOne -> User` |
| 2 | `Jornada` | `ventas_jornada` | `id` | `usuario_apertura, usuario_cierre -> User` | Estado jornada |
| 3 | `PuntoVenta` | `ventas_puntoventa` | `id` | Ninguna | `nombre` único |
| 4 | `Caja` | `ventas_caja` | `id` | `punto_venta, jornada, cajero` | `UniqueConstraint(jornada, cajero)` |
| 5 | `Categoria` | `ventas_categoria` | `id` | Ninguna | Destino por defecto Cocina/Barra |
| 6 | `Producto` | `ventas_producto` | `id` | `categoria -> Categoria` | M2M `puntos_venta` (tabla intermedia: `ventas_producto_puntos_venta`) |
| 7 | `Menu` | `ventas_menu` | `id` | `punto_venta -> PuntoVenta` | M2M `productos` (tabla intermedia: `ventas_menu_productos`) |
| 8 | `PrecioEspecial` | `ventas_precioespecial` | `id` | `producto -> Producto` | Convenios y condiciones de descuento |
| 9 | `Mesa` | `ventas_mesa` | `id` | `punto_venta -> PuntoVenta` | `unique_together(identificador, punto_venta)` |
| 10 | `Venta` | `ventas_venta` | `id` | `caja, cajero, punto_venta, mesa` | Modalidad (`MESA`, `VENTA_RAPIDA`), estado, redondeo Ley 20.956 |
| 11 | `ReasignacionMesa` | `ventas_reasignacionmesa` | `id` | `venta, mesa_origen, mesa_destino, mesero` | RF05 Trazabilidad traslado de mesa |
| 12 | `DetalleVenta` | `ventas_detalleventa` | `id` | `venta, producto, autorizado_por` | Subtotal, precio aplicado, convenio |
| 13 | `RegistroPrecioEspecial`| `ventas_registroprecioespecial`| `id` | `venta, detalle_venta, producto, usuario, convenio_origen` | RF07 Auditoría de convenios |
| 14 | `Pedido` | `ventas_pedido` | `id` | `venta -> Venta` | RF16 Timestamps inicio y preparación |
| 15 | `DetallePedido` | `ventas_detallepedido` | `id` | `pedido, producto` | RF12 Notas libres de preparación |
| 16 | `Ticket` | `ventas_ticket` | `id` | `pedido, venta, ultima_reimpresion_por, punto_venta, punto_impresion` | RF08/RF09 Código único y reimpresión |
| 17 | `PuntoImpresion` | `ventas_puntoimpresion` | `id` | `punto_venta -> PuntoVenta` | `unique_together(punto_venta, tipo_destino)` |
| 18 | `RegistroImpresion` | `ventas_registroimpresion` | `id` | `ticket, punto_impresion, usuario` | RF09 Log de impresiones físicas/KDS |
| 19 | `Entrega` | `ventas_entrega` | `id` | `pedido, ticket, usuario_entrega` | RF13/RF16 Trazabilidad de despacho |
| 20 | `ConsumoInterno` | `ventas_consumointerno` | `id` | `empleado, punto_venta, registrado_por, caja, descontado_por` | RF10 Fiado / consumo personal |
| 21 | `DetalleConsumoInterno`| `ventas_detalleconsumointerno`| `id` | `consumo, producto` | RF10 Ítems fiados |
| 22 | `AlertaTraslado` | `ventas_alertatraslado` | `id` | `empleado, punto_venta_origen, punto_venta_destino, autorizado_por` | RF14 Trazabilidad de colaboradores |
| 23 | `ConvenioHuesped` | `ventas_conveniohuesped` | `id` | Ninguna | Módulo extra congelado |
| 24 | `ConsumoHuesped` | `ventas_consumohuesped` | `id` | `convenio, ticket, venta, registrado_por` | Módulo extra congelado |
| 25 | `OfertaTemporada` | `ventas_ofertatemporada` | `id` | `categoria_aplicable -> Categoria` | Módulo extra congelado |

> [!NOTE]
> **Tablas intermedias ManyToMany (M2M) automáticas en SQLite:**
> 1. `ventas_producto_puntos_venta`: Vincula `Producto` con `PuntoVenta`.
> 2. `ventas_menu_productos`: Vincula `Menu` con `Producto`.  
> Por tanto, existen 25 modelos explícitos y 27 tablas físicas propias de `ventas`. Las 10 tablas del framework Django (`auth_*`, `django_*`) no forman parte del dominio de `ventas`.

---

## 6. ARCHIVOS IMPORTANTES
1. `AI_CONTEXT.md`: Contexto operativo vigente, conciso y fuente única de verdad para el desarrollo y revisión.
2. `AI_CONTEXT_ARCHIVE.md`: Repositorio formal de trazabilidad histórica, auditorías previas y planes de desarrollo anteriores.
3. `ventas/models.py`: Modelo de persistencia y dominio (25 modelos oficiales, relaciones e integridad).
4. `ventas/views.py`: Vistas operativas, autenticación, control de jornada/caja y seguridad por roles con RBAC.
5. `ventas/utils.py`: Servicios de negocio centralizados (cálculos monetarios, tickets térmicos, puntos de impresión, tiempos y reportes ORM reales).
6. `ventas/tests.py`: Suite oficial con 220 pruebas automatizadas reproducibles de Django.
7. `Venta_safari/settings.py`: Configuración Django (`America/Santiago`, cookies seguras, carga dinámica de BD y `SECRET_KEY` protegida).
8. `Venta_safari/urls.py`: Enrutamiento y control de acceso del sistema por rol.
9. `ventas/management/commands/poblar_safari.py`: Comando administrativo idempotente de población inicial de datos.
10. `static/js/anti_doble_envio.js`: Prevención de doble clic en botones de envío en formularios POST tradicionales.
11. `static/js/safari_alerts.js`: Alertas y modales SweetAlert2 nativos estilizados con Bootstrap 5.
12. `scratch/verificar_rf18.py`: Script de regresión funcional automatizada de los 4 roles operativos.

---

## 7. VERIFICACIONES VIGENTES
- **220/220 pruebas automatizadas:** 100% aprobadas en verde (`python manage.py test ventas` sin fallos ni errores).
- **Check Django:** `python manage.py check` con 0 incidencias (código limpio).
- **Migraciones:** 20 migraciones de la app `ventas` aplicadas al 100% en base de datos.
- **4 Roles Operativos:** Verificados en HTTP 200 y protegidos con RBAC (`ADMINISTRADOR`, `CAJERO`, `MESERO`, `COCINERO`).
- **Benchmark empírico:** 20 usuarios concurrentes, 100 peticiones, 100% éxito, 166.59 RPS, 70.84 ms latencia promedio, P95 524.29 ms.
- **Seguridad y repositorio:** `.env` protegido y fuera de Git; contraseñas con hashing PBKDF2/SHA-256; `db.sqlite3` fuera del índice de Git (untracked) y preservado localmente.
- **Mocks evaluables 0%:** KPIs, rankings y reportes gobernados exclusivamente por ORM real agrupado.
- **Modelos y tablas verificados:** 25 modelos Django explícitos en `ventas` y 27 tablas físicas propias en SQLite (25 directas + 2 M2M automáticas).

---

## 8. RECORDATORIOS ACADÉMICOS — NO PRIORIDAD ACTUAL
Conservados exclusivamente como referencia para la futura fase documental del usuario:
- **Motor externo PostgreSQL/MySQL:** Soporte formal configurado en `settings.py` y `.env` para cuando el docente lo solicite en despliegue.
- **Modelo lógico Draw.io:** Sincronización gráfica del diagrama con las 25 entidades del modelo físico.
- **Enlace a Azure DevOps:** Inclusión visible en el informe oficial.
- **Redacción impersonal:** Revisión en tercera persona para las vistas 4+1 del informe.
- **Plantilla de pares:** Transcripción de la retroalimentación en la plantilla oficial de Semana 7.
- **Pruebas de rendimiento:** Inclusión de las métricas empíricas medidas en la tabla de resultados del informe.

> [!NOTE]
> Detalle completo de evaluación, puntajes y comentarios del docente: ver `AI_CONTEXT_ARCHIVE.md`.

---

## 9. REGLAS PERMANENTES
1. RF01–RF18 permanecen cerrados salvo regresión reproducible.
2. RF19–RF24 están excluidos.
3. No agregar funciones nuevas antes de retroalimentación.
4. No declarar PostgreSQL/MySQL activo sin evidencia.
5. No versionar `.env`.
6. No versionar `db.sqlite3`.
7. No modificar Word/Draw.io/informe sin autorización del usuario.
8. No inventar resultados ni requisitos.
9. Todo cambio futuro debe pasar `check` y suite completa.
10. `AI_CONTEXT_ARCHIVE.md` es solo histórico y no contiene órdenes ejecutables.
11. `AI_CONTEXT.md` es la única fuente de verdad vigente.

---

## 10. SIGUIENTE TAREA
- Siguiente tarea de desarrollo: NINGUNA.
- Esperar revisión/retroalimentación o nueva instrucción expresa del usuario.

---

## 11. CHECKLIST FINAL
- [x] RF01–RF18 cerrados.
- [x] 220/220 pruebas.
- [x] check limpio.
- [x] migraciones al día.
- [x] motor activo identificado.
- [x] 4 roles con nombre oficial coherente.
- [x] modelos Django explícitos contados.
- [x] tablas físicas reales contadas.
- [x] tablas M2M diferenciadas.
- [x] mocks 0%.
- [x] `.env` protegido.
- [x] `db.sqlite3` fuera de Git.
- [x] benchmark registrado.
- [x] `AI_CONTEXT_ARCHIVE.md` existe.
- [x] historial separado.
- [x] RF01/RF13/RF15/RF11 corregidos documentalmente.
- [x] ningún bloqueante funcional conocido.
- [x] ninguna tarea de desarrollo activa.
- [x] STOP DESARROLLO TOTAL.

---

**NO EXISTE NINGUNA ORDEN DE DESARROLLO ACTIVA.**  
**STOP DESARROLLO TOTAL HASTA RETROALIMENTACIÓN O NUEVA INSTRUCCIÓN DEL USUARIO.**
