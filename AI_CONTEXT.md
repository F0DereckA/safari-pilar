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
- Motor actual: **SQLite**.
- Modelos/tablas de `ventas`: **25**.
- Roles operativos:
  - ADMINISTRADOR;
  - CAJERO;
  - MESERO;
  - COCINERO.
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
- Retroalimentación académica: recordatorio futuro, **NO prioridad actual**.

---

## 3. ALCANCE OFICIAL
- **RF01–RF18:** Incluidos y cerrados al 100% con persistencia real y pruebas automatizadas.
- **RF19–RF24:** Totalmente excluidos del alcance oficial.
- **Módulos extras:** Huéspedes, cabañas, desayuno y ofertas permanecen congelados y fuera del núcleo evaluable.

---

## 4. RESUMEN RF01–RF18

| Requerimiento | Nombre Oficial | Estado | Evidencia Técnica Principal | Cierre Suite |
| :--- | :--- | :---: | :--- | :---: |
| **RF01** | Gestión de Usuarios y Roles | **CERRADO** | Login por perfil, aislamiento RBAC, cambio de clave ISO/IEC 27400 | OK |
| **RF02** | Apertura y Cierre de Jornada | **CERRADO** | Jornada operativa con fecha local de hoy y bloqueo de días anteriores | OK |
| **RF03** | Apertura y Arqueo de Caja | **CERRADO** | Caja individual por cajero, fondo inicial opcional y arqueo en efectivo | OK |
| **RF04** | Gestión de Mesas por Local | **CERRADO** | CRUD de mesas por punto de venta con estados Libre/Ocupada/Inactiva | OK |
| **RF05** | Reasignación de Mesas | **CERRADO** | Traslado transaccional de venta entre mesas sin duplicación de comandas | OK (93/93) |
| **RF06** | Registro de Ventas y Cobro POS | **CERRADO** | Ventas en barra, cálculo de IVA y regla de redondeo oficial Ley 20.956 | OK |
| **RF07** | Precios Especiales y Convenios | **CERRADO** | Aplicación de convenios/beneficios autorizados con auditoría contable | OK (107/107) |
| **RF08** | Generación de Tickets con Código Único| **CERRADO** | Tickets térmicos digitales con QR, destino físico y control de copias | OK (116/116) |
| **RF09** | Gestión de Impresión Descentralizada | **CERRADO** | Enrutamiento automático a puntos de impresión (Cocina KDS / Barra KDS)| OK (127/127) |
| **RF10** | Consumo Interno / Fiado del Personal| **CERRADO** | Registro de consumos a colaboradores con saldo acumulado e historial | OK (137/137) |
| **RF11** | Asignación de Mesa o Venta Rápida | **CERRADO** | Conmutador de modalidades (Mesa, Venta Rápida POS, Para Llevar) | OK (145/145) |
| **RF12** | Comentarios Asociados a Productos | **CERRADO** | Notas libres de preparación reflejadas en comandas y tickets de cocina | OK (153/153) |
| **RF13** | Registro de Entrega de Productos | **CERRADO** | Despacho de platos por comensal, registro de usuario y hora exacta | OK (161/161) |
| **RF14** | Gestión de Puntos de Venta (Locales)| **CERRADO** | CRUD de locales gastronómicos, métricas individuales y alertas traslado | OK (172/172) |
| **RF15** | Posicionamiento de Menús por Local | **CERRADO** | Cartas gastronómicas diferenciadas por local con precios específicos | OK (185/185) |
| **RF16** | Control de Tiempos de Atención | **CERRADO** | Medición de tiempos de espera, cola y preparación culinaria KDS | OK (197/197) |
| **RF17** | Gestión de Ocupación de Mesas | **CERRADO** | Monitoreo en vivo de mesas ocupadas, cronómetro y tasa de rotación | OK (207/207) |
| **RF18** | Reportes y Estadísticas Reales | **CERRADO** | Dashboard con 0% mocks, filtros fecha/local, Top 10 y exportación Word/Excel| OK (220/220) |

---

## 5. MODELO DE DATOS VIGENTE
El modelo de persistencia actual cuenta exactamente con **25 entidades/modelos** en la app `ventas` con integridad referencial completa y restricciones validadas:

| # | Modelo Django | Tabla Física en BD | PK | Claves Foráneas (FK) | Restricciones / Relaciones |
| :---: | :--- | :--- | :---: | :--- | :--- |
| 1 | `PerfilEmpleado` | `ventas_perfilempleado` | `id` | `punto_venta_actual -> PuntoVenta` | `OneToOne -> User` |
| 2 | `Jornada` | `ventas_jornada` | `id` | `usuario_apertura, usuario_cierre -> User` | Estado jornada |
| 3 | `PuntoVenta` | `ventas_puntoventa` | `id` | Ninguna | `nombre` único |
| 4 | `Caja` | `ventas_caja` | `id` | `punto_venta, jornada, cajero` | `UniqueConstraint(jornada, cajero)` |
| 5 | `Categoria` | `ventas_categoria` | `id` | Ninguna | Destino por defecto Cocina/Barra |
| 6 | `Producto` | `ventas_producto` | `id` | `categoria -> Categoria` | M2M `puntos_venta <-> PuntoVenta` |
| 7 | `Menu` | `ventas_menu` | `id` | `punto_venta -> PuntoVenta` | M2M `productos <-> Producto` |
| 8 | `PrecioEspecial` | `ventas_precioespecial` | `id` | `producto -> Producto` | Convenios/descuentos |
| 9 | `Mesa` | `ventas_mesa` | `id` | `punto_venta -> PuntoVenta` | `unique_together(identificador, punto_venta)` |
| 10 | `Venta` | `ventas_venta` | `id` | `caja, cajero, punto_venta, mesa` | Modalidad, estado, redondeo Ley 20.956 |
| 11 | `ReasignacionMesa` | `ventas_reasignacionmesa` | `id` | `venta, mesa_origen, mesa_destino, mesero` | RF05 Trazabilidad traslado |
| 12 | `DetalleVenta` | `ventas_detalleventa` | `id` | `venta, producto, autorizado_por` | Subtotal, precio aplicado, convenio |
| 13 | `RegistroPrecioEspecial`| `ventas_registroprecioespecial`| `id` | `venta, detalle_venta, producto, usuario, convenio_origen` | RF07 Auditoría convenios |
| 14 | `Pedido` | `ventas_pedido` | `id` | `venta -> Venta` | RF16 Timestamps inicio/listo |
| 15 | `DetallePedido` | `ventas_detallepedido` | `id` | `pedido, producto` | RF12 Notas libres de preparación |
| 16 | `Ticket` | `ventas_ticket` | `id` | `pedido, venta, ultima_reimpresion_por, punto_venta, punto_impresion` | RF08/RF09 Código único y reimpresión |
| 17 | `PuntoImpresion` | `ventas_puntoimpresion` | `id` | `punto_venta -> PuntoVenta` | `unique_together(punto_venta, tipo_destino)` |
| 18 | `RegistroImpresion` | `ventas_registroimpresion` | `id` | `ticket, punto_impresion, usuario` | RF09 Log de impresiones físicas/KDS |
| 19 | `Entrega` | `ventas_entrega` | `id` | `pedido, ticket, usuario_entrega` | RF13/RF16 Trazabilidad despacho |
| 20 | `ConsumoInterno` | `ventas_consumointerno` | `id` | `empleado, punto_venta, registrado_por, caja, descontado_por` | RF10 Fiado / consumo personal |
| 21 | `DetalleConsumoInterno`| `ventas_detalleconsumointerno`| `id` | `consumo, producto` | RF10 Ítems fiados |
| 22 | `AlertaTraslado` | `ventas_alertatraslado` | `id` | `empleado, punto_venta_origen, punto_venta_destino, autorizado_por` | RF14 Trazabilidad colaboradores |
| 23 | `ConvenioHuesped` | `ventas_conveniohuesped` | `id` | Ninguna | Módulo extra congelado |
| 24 | `ConsumoHuesped` | `ventas_consumohuesped` | `id` | `convenio, ticket, venta, registrado_por` | Módulo extra congelado |
| 25 | `OfertaTemporada` | `ventas_ofertatemporada` | `id` | `categoria_aplicable -> Categoria` | Módulo extra congelado |

---

## 6. ARCHIVOS IMPORTANTES
- `ventas/models.py`: Modelo de persistencia y dominio (25 modelos oficiales, relaciones e integridad).
- `ventas/views.py`: Vistas operativas, autenticación, control de jornada/caja y seguridad por roles.
- `ventas/utils.py`: Servicios de negocio centralizados (cálculos, tickets, impresoras, tiempos y reportes).
- `ventas/tests.py`: Suite oficial con 220 pruebas automatizadas reproducibles de Django.
- `Venta_safari/settings.py`: Configuración Django (`America/Santiago`, cookies seguras, carga dinámica de BD y SECRET_KEY).
- `Venta_safari/urls.py`: Enrutamiento y control de acceso del sistema.
- `ventas/management/commands/poblar_safari.py`: Comando idempotente de población inicial de datos.
- `static/js/safari_alerts.js`: Alertas y modales SweetAlert2 nativos de Bootstrap 5.
- `static/js/anti_doble_envio.js`: Prevención de doble clic en botones de envío en formularios POST.
- `AI_CONTEXT_ARCHIVE.md`: Repositorio formal de trazabilidad histórica, auditorías previas y planes de desarrollo anteriores.

---

## 7. VERIFICACIONES VIGENTES
- **220/220 pruebas automatizadas:** 100% aprobadas en verde (`python manage.py test ventas` sin fallos ni errores).
- **Check Django:** `python manage.py check` con 0 incidencias (código limpio).
- **Migraciones:** 20 migraciones de la app `ventas` aplicadas al 100% en base de datos.
- **4 Roles Operativos:** Verificados en HTTP 200 y protegidos con RBAC (`ADMINISTRADOR`, `CAJERO`, `MESERO`, `COCINA`).
- **Benchmark empírico:** 20 usuarios concurrentes, 100 peticiones, 100% éxito, 166.59 RPS, 70.84 ms latencia promedio, P95 524.29 ms.
- **Seguridad y repositorio:** `.env` protegido y fuera de Git; contraseñas con hashing PBKDF2/SHA-256; `db.sqlite3` fuera del índice de Git (untracked) y preservado localmente.
- **Mocks evaluables 0%:** KPIs, rankings y reportes gobernados exclusivamente por ORM real agrupado.

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
> Detalle completo de la retroalimentación: ver `AI_CONTEXT_ARCHIVE.md`.

---

## 9. REGLAS PERMANENTES
1. No desarrollar RF19–RF24;
2. No agregar funciones nuevas antes de retroalimentación;
3. No reabrir RF01–RF18 salvo regresión reproducible;
4. No declarar PostgreSQL activo sin evidencia;
5. No versionar `.env` ni `db.sqlite3`;
6. No modificar Word/Draw.io/informe sin autorización del usuario;
7. No inventar resultados;
8. Cualquier cambio futuro debe pasar `check` + suite completa;
9. El archivo histórico `AI_CONTEXT_ARCHIVE.md` no contiene órdenes ejecutables.

---

## 10. SIGUIENTE TAREA
- Siguiente tarea de desarrollo: NINGUNA.
- Esperar revisión/retroalimentación o nueva instrucción expresa del usuario.

---

## 11. CHECKLIST FINAL
- [x] RF01–RF18 cerrados.
- [x] 220/220 pruebas automatizadas aprobadas.
- [x] check limpio (0 incidencias).
- [x] migraciones al día (20 aplicadas).
- [x] 4 roles operativos verificados con RBAC.
- [x] 25 modelos auditados y mapeados 1:1.
- [x] mocks 0% en flujos evaluables.
- [x] `.env` protegido y fuera de Git.
- [x] `db.sqlite3` fuera de Git y conservado localmente.
- [x] benchmark real registrado empíricamente.
- [x] ningún bloqueante funcional conocido.
- [x] no existe ninguna orden de desarrollo activa.
- [x] historial separado en `AI_CONTEXT_ARCHIVE.md`.
- [x] Normalización estructural completada.
- [x] Historial movido a AI_CONTEXT_ARCHIVE.md.
- [x] AI_CONTEXT.md contiene solo estado vigente.
- [x] STOP DESARROLLO TOTAL.

---

**NO EXISTE NINGUNA ORDEN ACTIVA.**  
**STOP DESARROLLO TOTAL HASTA RETROALIMENTACIÓN O NUEVA INSTRUCCIÓN DEL USUARIO.**
