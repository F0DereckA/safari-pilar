# AI_CONTEXT_ARCHIVE — HISTORIAL TÉCNICO / NO EJECUTAR

> [!NOTE]
> Este archivo conserva la trazabilidad histórica de desarrollo, auditorías, planes maestros y retroalimentación académica del proyecto. Ningún verbo imperativo, pendiente, riesgo, plan, orden o siguiente paso contenido aquí constituye trabajo vigente. La única fuente operativa y de contexto activo es `AI_CONTEXT.md`.

---

### HISTÓRICO — ORDEN DE CONSOLIDACIÓN FINAL YA EJECUTADA / NO VIGENTE

> [!IMPORTANT]
> Esta orden fue ejecutada en una fase anterior. Los RF01–RF18 se encuentran funcionalmente cerrados (220/220 pruebas OK). Se conserva exclusivamente como trazabilidad histórica y NO constituye trabajo pendiente.

## FASE A — RECONCILIACIÓN DEL AI_CONTEXT

1. Mantener como estado vigente:
   - RF01–RF18: COMPLETADOS.
   - RF18: COMPLETADO Y CERRADO.
   - suite vigente: 220/220 pruebas.
2. Todo bloque que mencione 15, 20, 25, 37, 41, 45, 50, 83, 84, 93, 107, 116, 127, 137, 145, 153, 161, 172, 185, 197 o 207 pruebas debe:
   - conservarse si sirve como historial;
   - marcarse claramente como **HISTÓRICO / NO VIGENTE**;
   - no presentarse como estado actual.
3. Corregir inconsistencias internas:
   - RF09 debe quedar coherente con su cierre real reportado de 127/127, no 125/125.
   - `## 3. estado actual` debe reflejar 220/220, no 25/25.
   - `## 6. errores actuales` no debe listar RF05, RF07, RF10, RF13/16, RF17 ni RF18 como pendientes.
   - `## 7`, `## 8` y `## 10` no deben indicar que RF07 es el siguiente paso.
   - las reglas permanentes no deben tratar Semana 10/11 como prioridad actual.
4. Mantener el Mapa de Convergencia 06-Oct únicamente como evidencia histórica, con encabezado explícito:
   - `HISTÓRICO — estado al 06/10/2026`.
5. No borrar historial útil; separarlo del estado vigente.

## FASE B — AUDITORÍA TÉCNICA FINAL RF01–RF18

Ejecutar y registrar resultados exactos:

1. `python manage.py check`
2. `python manage.py test ventas`
3. `python manage.py showmigrations`
4. confirmar número exacto actual de pruebas;
5. confirmar todas las migraciones aplicadas;
6. confirmar motor de BD realmente activo;
7. revisar configuración `DEBUG`;
8. revisar origen real de `SECRET_KEY`;
9. revisar `.env`, `.env.example` y `.gitignore`;
10. revisar si `db.sqlite3` sigue versionado en Git;
11. revisar si quedan mocks, fallbacks demo o datos hardcodeados en flujos evaluables;
12. revisar errores 400 / 403 / 404 / 500;
13. revisar CSRF, permisos y control por rol;
14. revisar doble envío;
15. revisar concurrencia;
16. revisar soft-delete / protección histórica;
17. revisar que ventas, pedidos, tickets, entregas, consumos y reportes provengan de BD real;
18. revisar que Mesa/Cuenta Abierta, KDS Cocina, KDS Barra y caja sigan estables;
19. verificar manualmente:
   - ADMINISTRADOR;
   - CAJERO;
   - MESERO;
   - COCINERO.
20. registrar cada hallazgo como:
   - OK;
   - CORREGIDO;
   - PENDIENTE;
   - BLOQUEANTE.

## FASE C — MOTOR DE BASE DE DATOS

1. Determinar qué motor corre realmente hoy.
2. Si sigue siendo SQLite:
   - no declarar PostgreSQL/MySQL como implementado;
   - registrar SQLite como entorno actual;
   - dejar pendiente evidencia real de motor externo para la entrega.
3. Si PostgreSQL/MySQL ya está configurado:
   - ejecutar `migrate`;
   - ejecutar `check`;
   - ejecutar `test ventas`;
   - registrar evidencia real.
4. No modificar el motor a ciegas ni romper el entorno funcional.

## FASE D — MODELO DE DATOS REAL

1. Auditar `ventas/models.py` completo.
2. Contar el número real de modelos/tablas actuales.
3. No asumir que siguen siendo 19 entidades.
4. Identificar todas las entidades agregadas después del modelo inicial, incluyendo cuando correspondan:
   - ReasignacionMesa;
   - RegistroPrecioEspecial;
   - PuntoImpresion;
   - RegistroImpresion;
   - cualquier otra entidad nueva vigente.
5. Preparar una lista oficial 1:1:
   - modelo Django;
   - tabla física;
   - PK;
   - FK;
   - relaciones;
   - restricciones.
6. No modificar todavía Word ni Draw.io; solo dejar la información preparada.

## FASE E — SEGURIDAD Y CONFIGURACIÓN

1. Verificar si `SECRET_KEY` sigue hardcodeada.
2. Verificar `DEBUG`.
3. Verificar configuración de cookies/sesión.
4. Verificar rate limiting.
5. Verificar cambio obligatorio de contraseña.
6. Verificar expiración interna de 180 días.
7. Mantener la regla:
   - 180 días = política interna del proyecto;
   - no atribuirla como obligación específica de ISO/IEC 27400.
8. Verificar que ningún secreto real quede en repositorio.

## FASE F — PRUEBAS DE RENDIMIENTO

1. Revisar qué pruebas de carga existen realmente.
2. Conservar únicamente resultados medidos.
3. No inventar resultados de 50/100 usuarios si no se ejecutaron.
4. Preparar plan reproducible para:
   - 20 usuarios;
   - 50 usuarios;
   - 100 usuarios;
   únicamente si el entorno permite ejecutarlo sin comprometer el sistema.
5. Registrar:
   - promedio;
   - P95;
   - RPS;
   - tasa de éxito;
   - errores;
   - CPU/RAM si la herramienta lo permite.
6. Si solo existe prueba de 20 usuarios, dejarlo explícito.

## FASE G — EVIDENCIAS PARA ENTREGA 3

Preparar, sin editar aún el informe oficial:

1. tabla RF01–RF18 con:
   - requerimiento;
   - estado;
   - ruta/vista;
   - modelo(s);
   - prueba(s);
   - evidencia sugerida.
2. lista de capturas necesarias.
3. lista de endpoints principales.
4. lista de pruebas automatizadas por RF.
5. lista de controles de seguridad.
6. lista de métricas de rendimiento reales.
7. lista de entidades finales del modelo.
8. enlace Azure DevOps pendiente de validar.
9. recordatorio de redacción impersonal.
10. recordatorio de plantilla oficial de pares.

## FASE H — CRITERIO DE CIERRE DE ESTA ORDEN

Esta orden termina solamente cuando Antigravity devuelva:

- `AI_CONTEXT.md` reconciliado;
- estado vigente coherente en todo el archivo;
- 220/220 o nuevo conteo exacto confirmado;
- `manage.py check` limpio;
- resultado de `showmigrations`;
- motor BD identificado;
- lista de pendientes reales;
- conteo real de modelos/tablas;
- estado de SECRET_KEY / DEBUG / .env / Git;
- estado de mocks residuales;
- resumen de rendimiento disponible;
- matriz de evidencias RF01–RF18.

Después de eso:
- DETENER.
- No modificar Word, Draw.io ni informe oficial sin instrucción del usuario.
- Devolver `AI_CONTEXT.md` a ChatGPT para revisión final.

---

# HISTÓRICO — SANEAMIENTO DOCUMENTAL 100% EJECUTADO / CIERRE DEFINITIVO

> [!IMPORTANT]
> Esta orden fue ejecutada por completo. Se conserva como trazabilidad y NO constituye una orden activa.

## A. REGLA DE SANEAMIENTO TOTAL

Revisar `AI_CONTEXT.md` completo, de la primera a la última línea.

Para cada bloque anterior al estado vigente:
1. conservar hechos, fechas, resultados y decisiones históricas;
2. transformar encabezados imperativos en encabezados históricos;
3. transformar frases en presente como “falta”, “pendiente”, “debe”, “avanzar”, “implementar”, “siguiente paso”, “orden actual” a redacción pasada cuando ya fueron resueltas;
4. nunca permitir que un bloque histórico use la expresión “orden vigente”;
5. cuando una brecha histórica ya fue corregida, indicarlo como:
   - `HISTÓRICO — brecha registrada en esa fecha; resuelta posteriormente`;
6. no borrar evidencia útil;
7. no alterar hechos técnicos históricos ni conteos de pruebas históricos.

## B. CORRECCIONES OBLIGATORIAS YA IDENTIFICADAS

### B1. Antigua orden final pre-revisión
En el bloque:
`HISTÓRICO — ORDEN FINAL PRE-REVISIÓN YA EJECUTADA / NO VIGENTE`

cambiar cualquier frase equivalente a:
`Esta es la única orden vigente...`

por:
`Esta fue una orden vigente en una fase anterior. Se conserva únicamente como trazabilidad histórica y NO debe ejecutarse.`

### B2. Plan Funcional histórico
Dentro de:
`PLAN FUNCIONAL PRIORITARIO RF01–RF18 — ROBUSTEZ OPERACIONAL (HISTÓRICO / REFERENCIA)`

cambiar:
`ORDEN DE EJECUCIÓN AUTORIZADO`

por:
`HISTÓRICO — ORDEN DE EJECUCIÓN RF05–RF18 YA EJECUTADA / NO VIGENTE`

y agregar inmediatamente:
`Todo el contenido de esta subsección describe la secuencia usada durante el desarrollo y no constituye trabajo pendiente.`

### B3. Semana 10
Dentro de:
`HISTÓRICO — HITOS SEMANA 10 Y SEMANA 11 YA COMPLETADOS`

cambiar:
- `Estado actual frente a Semana 10` -> `Estado registrado en ese momento frente a Semana 10`.
- cualquier frase `Falta...` -> `En ese momento faltaba...`.
- `Orden técnica Semana 10` -> `HISTÓRICO — Orden técnica Semana 10 ya ejecutada`.

La subsección debe conservar sus pasos como evidencia, pero no debe sonar como una orden actual.

### B4. Semana 11
Cambiar:
`Qué debe quedar adelantado antes de la clase del 20/10`

por:
`HISTÓRICO — Objetivos definidos antes de la clase del 20/10, ya ejecutados`

Cambiar cualquier “debe”, “consolidar”, “confirmar”, etc. que aparezca como instrucción vigente a formulación histórica cuando corresponda:
- `se definió como objetivo...`
- `se debía confirmar...`
- `posteriormente quedó completado...`

No alterar los resultados reales 41/41, 45/45, 50/50.

### B5. Mapa de Convergencia 06-Oct
Dentro del bloque ya marcado:
`HISTÓRICO — estado al 06/10/2026`

renombrar las subsecciones:

- `IMPLEMENTADO PERO REQUIERE CORRECCIÓN`
  -> `HISTÓRICO — IMPLEMENTADO PERO REQUERÍA CORRECCIÓN AL 06-OCT; RESUELTO POSTERIORMENTE`

- `TODAVÍA MOCK / HARDCODEADO`
  -> `HISTÓRICO — MOCK / HARDCODEADO AL 06-OCT; RESUELTO POSTERIORMENTE`

- `RIESGOS DE INTEGRIDAD`
  -> `HISTÓRICO — RIESGOS DE INTEGRIDAD IDENTIFICADOS AL 06-OCT`

- `RIESGOS DE SEGURIDAD / REPOSITORIO`
  -> `HISTÓRICO — RIESGOS DE SEGURIDAD / REPOSITORIO IDENTIFICADOS AL 06-OCT`

- `PRUEBAS FALTANTES`
  -> `HISTÓRICO — PRUEBAS QUE FALTABAN AL 06-OCT; CUBIERTAS POSTERIORMENTE`

- `REGLA FUNCIONAL PENDIENTE — MESA / CUENTA ABIERTA`
  -> `HISTÓRICO — REGLA FUNCIONAL QUE ESTABA PENDIENTE AL 06-OCT; RESUELTA`

- `SIGUIENTE PASO RECOMENDADO`
  -> `HISTÓRICO — SIGUIENTE PASO RECOMENDADO AL 06-OCT; YA EJECUTADO`

También cambiar:
`Estado Actual`
por:
`Estado registrado al 06-Oct`

cuando aparezca dentro de ese bloque.

### B6. Sección `## 9`
Cambiar:
`## 9. HISTÓRICO — Auditoría de Convergencia y Mapa de Convergencia 06-Oct`

por:
`## 9. HISTÓRICO — Auditoría de Convergencia y Mapa de Convergencia 06-Oct`

## C. RECORDATORIOS DE EVALUACIÓN — DEBEN QUEDAR SOLO COMO RECORDATORIO

El usuario decidió expresamente que esta parte **NO ES PRIORIDAD ACTUAL**.

Mantener toda la retroalimentación, puntajes, comentarios del profesor y notas del usuario, pero neutralizar etiquetas que parezcan órdenes vigentes.

Dentro del bloque:
`RECORDATORIO ACADÉMICO / NO PRIORIDAD ACTUAL`

cambiar encabezados como:
- `[URGENTE - CRÍTICO]`
- `[ALTA PRIORIDAD]`
- `[MEDIA-ALTA PRIORIDAD]`
- `[RECORDATORIO FORMATO]`
- `[CORRECCIÓN FORMATO]`
- `[GESTIÓN ACADÉMICA]`
- `[SEGUIMIENTO]`

por una forma histórica, por ejemplo:
`[PRIORIDAD INDICADA EN LA RETROALIMENTACIÓN ORIGINAL — NO PRIORIDAD ACTUAL]`

Cambiar:
`Acción Requerida para Entrega 3:`

por:
`Acción sugerida/solicitada en la retroalimentación original para una futura fase documental:`

Conservar literalmente:
- puntajes obtenidos;
- observaciones del docente;
- notas del usuario;
- contenido técnico del recordatorio.

NO ejecutar ninguna de esas acciones ahora.

## D. ESTADO VIGENTE ÚNICO

Al terminar, la única fuente de verdad vigente debe ser:

- RF01–RF18: **COMPLETADOS AL 100%**.
- Suite: **220/220**.
- `python manage.py check`: **0 incidencias**.
- Migraciones `ventas`: **20 aplicadas**.
- Motor actual: **SQLite**.
- Modelos/tablas `ventas`: **25**.
- Roles: ADMINISTRADOR, CAJERO, MESERO, COCINERO.
- Mocks evaluables: **0%**.
- `.env`: protegido.
- `db.sqlite3`: fuera del índice Git y conservado localmente.
- Benchmark vigente: 166.59 RPS, 70.84 ms promedio, P95 524.29 ms, 100/100 exitosas.
- Bloqueantes funcionales: **ninguno conocido**.
- Tarea de desarrollo: **NINGUNA**.
- Fase documental: pendiente de autorización expresa del usuario.
- Recordatorios de evaluación: conservados, **NO prioridad actual**.

## E. BARRIDO FINAL OBLIGATORIO

Antes de cerrar, revisar el archivo completo buscando semánticamente cualquier texto histórico que aún parezca presente/activo.

No limitarse a una lista literal.

Debe detectarse y corregirse cualquier uso histórico de conceptos como:
- orden vigente;
- orden actual;
- siguiente paso;
- siguiente tarea;
- pendiente;
- falta;
- debe implementarse;
- debe completarse;
- avanzar;
- urgente;
- crítico;
- alta prioridad;
- acción requerida;

cuando el contexto real indique que ya fue ejecutado o que solo corresponde a evaluación futura.

Excepción:
- `## 10. siguiente tarea` vigente puede existir únicamente para declarar **NINGUNA**.
- los términos pueden permanecer en citas literales del docente o notas históricas si quedan inequívocamente contextualizados como cita/registro pasado.

## F. VERIFICACIÓN DE CONSISTENCIA

Al finalizar revisar expresamente:

1. El bloque de estado actual.
2. El checklist final.
3. `## 6. errores actuales`.
4. `## 8. respuesta de ChatGPT`.
5. `## 9` histórico.
6. `## 10. siguiente tarea`.
7. `## 12. reglas permanentes`.
8. Todos los encabezados `HISTÓRICO`.
9. Todo el bloque de retroalimentación académica.
10. Todo el Mapa de Convergencia 06-Oct.

No modificar:
- código;
- models.py;
- views.py;
- utils.py;
- templates;
- migraciones;
- BD;
- Word;
- Draw.io;
- informe.

## G. AUTOCIERRE DE ESTA MISMA ORDEN

Cuando el saneamiento esté terminado:

1. cambiar el encabezado de esta sección:
   `# ORDEN VIGENTE DE SANEAMIENTO DOCUMENTAL 100% — ÚLTIMA EJECUCIÓN Y AUTOCIERRE`

   por:

   `# HISTÓRICO — SANEAMIENTO DOCUMENTAL 100% EJECUTADO / CIERRE DEFINITIVO`

2. reemplazar esta advertencia inicial por:
   `Esta orden fue ejecutada por completo. Se conserva como trazabilidad y NO constituye una orden activa.`

3. En `## 8. respuesta de ChatGPT`, dejar:
   - `No existe ninguna orden de desarrollo vigente.`
   - `Proyecto congelado para revisión y retroalimentación.`
   - `STOP DESARROLLO TOTAL hasta nueva instrucción expresa del usuario.`

4. En `## 10. siguiente tarea`, dejar exclusivamente:
   - `Siguiente tarea de desarrollo: NINGUNA.`
   - `Esperar revisión/retroalimentación o nueva instrucción expresa del usuario.`

5. En el checklist final confirmar:
   - `[x] No existe ninguna orden activa anterior.`
   - `[x] Todo contenido imperativo histórico está contextualizado como pasado/no vigente.`
   - `[x] Recordatorios académicos preservados sin prioridad operativa actual.`
   - `[x] STOP DESARROLLO TOTAL.`

## CRITERIO REAL DE 100%

No declarar esta tarea terminada por haber agregado una advertencia general.

Solo se considera 100% cuando:
- todo encabezado histórico imperativo está renombrado o contextualizado;
- ninguna frase histórica puede confundirse razonablemente con una orden actual;
- las prioridades académicas antiguas no aparentan ser prioridad operativa;
- existe una sola fuente de verdad vigente;
- esta propia orden queda autocerrada como histórica;
- no queda ninguna tarea de desarrollo activa.

Después de eso: **STOP DESARROLLO TOTAL**.

---

# HISTÓRICO — ORDEN DEFINITIVA DE LIMPIEZA TEXTUAL YA EJECUTADA / NO VIGENTE

> [!IMPORTANT]
> Esta fue una orden vigente en una fase anterior. Se conserva exclusivamente como trazabilidad histórica y **NO debe ejecutarse**.

## TAREA 1 — CORREGIR `## 8. respuesta de ChatGPT`

Reemplazar cualquier referencia a una orden antigua, especialmente:

`PREPARAR PROYECTO PARA REVISIÓN Y RETROALIMENTACIÓN`

por una formulación vigente:

- **orden que estuvo vigente en esa fase: ORDEN DEFINITIVA PARA ANTIGRAVITY — ÚLTIMA LIMPIEZA TEXTUAL Y CIERRE TOTAL**;
- no ejecutar órdenes históricas;
- no desarrollar nuevas funciones;
- no modificar documentos académicos todavía;
- después de esta limpieza: **STOP DESARROLLO**.

## TAREA 2 — CORREGIR EL BLOQUE HISTÓRICO DE PREPARACIÓN

El bloque:

`# HISTÓRICO — ORDEN DE PREPARACIÓN PARA REVISIÓN YA EJECUTADA / NO VIGENTE`

debe conservarse por trazabilidad, pero dentro de él todavía aparece una frase que dice:

`Esta es la orden vigente.`

Cambiarla por:

`Esta fue una orden vigente en una fase anterior. Se conserva únicamente como trazabilidad histórica y NO debe ejecutarse.`

No eliminar el resto del bloque.

## TAREA 3 — BLINDAR EL PLAN MAESTRO HISTÓRICO

Debajo del encabezado:

`### PLAN MAESTRO RF07–RF18 — HISTÓRICO / PLAN YA EJECUTADO`

agregar inmediatamente:

> [!CAUTION]
> Todo texto imperativo, secuencia de implementación, “detener”, “no iniciar RF siguiente” o instrucción contenida en este bloque corresponde únicamente al historial de desarrollo. **NO constituye una orden activa.**

No borrar el detalle histórico de RF07–RF18.

## TAREA 4 — BLINDAR OTROS BLOQUES HISTÓRICOS

Aplicar la misma regla a:
- Plan Funcional Prioritario RF01–RF18;
- Mapa de Convergencia 06-Oct;
- Semana 10 / Semana 11;
- órdenes antiguas de RF05/RF07/etc.;
- cualquier bloque que incluya “siguiente paso”, “pendiente”, “implementar” o “detener” pero que ya esté resuelto.

No es necesario reescribir todo el historial. Basta con que el encabezado o una advertencia deje inequívoco que:
- es histórico;
- no es una instrucción vigente;
- el estado actual prevalece.

## TAREA 5 — DEJAR UNA SOLA FUENTE DE VERDAD

Verificar que el estado vigente final sea solamente:

- RF01–RF18: **100% COMPLETADOS**.
- Suite: **220/220 pruebas aprobadas**.
- `python manage.py check`: **0 incidencias**.
- Migraciones `ventas`: **20 aplicadas**.
- Motor actual: **SQLite**.
- Modelos/tablas `ventas`: **25**.
- Roles: ADMINISTRADOR, CAJERO, MESERO y COCINERO.
- Mocks evaluables: **0%**.
- `.env`: protegido.
- `db.sqlite3`: fuera de Git y conservado localmente.
- Benchmark vigente:
  - 20 usuarios;
  - 100 peticiones;
  - 100% éxito;
  - 166.59 RPS;
  - 70.84 ms promedio;
  - P95 524.29 ms.
- Bloqueantes funcionales: **ninguno conocido**.
- Siguiente tarea de desarrollo: **NINGUNA**.

## TAREA 6 — CHECKLIST FINAL

Confirmar que `## CHECKLIST FINAL PRE-REVISIÓN` permanezca con todos sus ítems comprobados.

Agregar dos ítems si todavía no existen:

- [x] No existe ninguna orden activa anterior.
- [x] Todo contenido imperativo histórico está contextualizado como pasado/no vigente.
- [x] Recordatorios académicos preservados sin prioridad operativa actual.
- [x] STOP DESARROLLO TOTAL.

## TAREA 7 — VERIFICACIÓN DOCUMENTAL FINAL

Buscar en todo `AI_CONTEXT.md` las expresiones:

- `Esta es la orden vigente`
- `siguiente paso RF07`
- `no iniciar RF08`
- `RF05 pendiente`
- `cada RF restante`
- `DEBE QUEDAR COMPLETA`
- `AVANZAR PARCIALMENTE`
- `siguiente paso recomendado`

Para cada coincidencia:
- si pertenece a historial, mantenerla solo dentro de un bloque claramente marcado como histórico;
- si aparece como instrucción vigente, corregirla;
- no borrar evidencia histórica.

## CRITERIO DE CIERRE DEFINITIVO

La tarea termina cuando:

1. existió una sola orden ejecutada en esa fase;
2. no hubo contradicciones entre la orden y los bloques históricos;
3. `## 8. respuesta de ChatGPT` apuntó a esa orden de limpieza;
4. la antigua orden de preparación ya no dijo “Esta es la orden vigente”;
5. el Plan Maestro RF07–RF18 contuvo advertencia de historial;
6. el checklist confirmó el cierre definitivo y STOP desarrollo;
7. no se modificó ningún archivo funcional del sistema;
8. no se modificó Word, Draw.io ni informe;
9. no se agregaron RF ni funcionalidades;
10. `AI_CONTEXT.md` queda guardado y devuelto para revisión.

### DESPUÉS DE CUMPLIR TODO LO ANTERIOR

**STOP DESARROLLO TOTAL.**

No realizar ningún cambio adicional hasta:
- nueva instrucción expresa del usuario; o
- retroalimentación/revisión que identifique un problema reproducible.

---

# HISTÓRICO — ORDEN FINAL PRE-REVISIÓN YA EJECUTADA / NO VIGENTE

> [!IMPORTANT]
> Esta fue una orden vigente en una fase anterior. Se conserva únicamente como trazabilidad histórica y NO debe ejecutarse.

## 1. UNIFICAR EL ESTADO VIGENTE

Dejar claramente establecido en la parte superior y en `## 3. estado actual`:

- RF01–RF18: **COMPLETADOS AL 100%**.
- Suite vigente: **220/220 pruebas aprobadas**.
- `python manage.py check`: **0 incidencias**.
- Migraciones `ventas`: **20 aplicadas**.
- Motor activo: **SQLite**.
- Modelos/tablas `ventas`: **25**.
- Roles operativos: ADMINISTRADOR, CAJERO, MESERO, COCINERO.
- Mocks en flujos evaluables: **0%**.
- Benchmark de regresión vigente:
  - 20 usuarios concurrentes;
  - 100 peticiones;
  - 100% éxito;
  - 166.59 RPS;
  - 70.84 ms promedio;
  - P95 524.29 ms.
- `db.sqlite3`: fuera del índice Git y conservado localmente.
- `.env`: protegido y no rastreado.

## 2. MARCAR COMO HISTÓRICO TODO LO YA EJECUTADO

Marcar explícitamente como `HISTÓRICO / NO VIGENTE`:

- Orden de Consolidación Final anterior.
- Plan Maestro RF07–RF18.
- Plan Funcional Prioritario RF01–RF18.
- Orden de ejecución RF05 -> RF07 -> RF10 -> RF13/16 -> RF17 -> RF18.
- Mapa de Convergencia 06-Oct.
- Plan académico Semana 10 / Semana 11.
- cualquier instrucción antigua del tipo:
  - “siguiente paso RF07”;
  - “detener antes de RF08”;
  - “RF05 pendiente”;
  - “cada RF restante debe implementarse”.

No eliminar información histórica útil. Solo evitar que pueda confundirse con una orden vigente.

## 3. CORREGIR SEMANA 10 / SEMANA 11

Cambiar el encabezado:

`PLAN ACADÉMICO DE RECUPERACIÓN — SEMANA 10 Y AVANCE SEMANA 11`

por:

`HISTÓRICO — HITOS SEMANA 10 Y SEMANA 11 YA COMPLETADOS`

Dentro de ese bloque:
- conservar resultados;
- conservar pruebas históricas 37/37, 41/41, 45/45, 50/50;
- dejar claro que son conteos históricos y no el estado actual;
- no dejar frases como “DEBE QUEDAR COMPLETA” o “AVANZAR PARCIALMENTE” como órdenes activas.

## 4. ACTUALIZAR `## 3. ESTADO ACTUAL`

La siguiente fase debe quedar descrita exactamente como:

**“Preparación para revisión y retroalimentación. Desarrollo funcional detenido. Fase documental pendiente de autorización expresa del usuario.”**

No poner “Entrega 3” como prioridad actual.

## 5. ACTUALIZAR `## 4. ARCHIVOS IMPORTANTES`

Corregir `tests.py`.

Texto antiguo:
- “Cubre los 15 escenarios clave…”

Texto vigente:
- “Suite oficial de 220 pruebas automatizadas que cubre RF01–RF18, seguridad, permisos, concurrencia, persistencia, tickets, impresión, consumo interno, tiempos, ocupación, reportes y regresión.”

Verificar también que las descripciones de:
- `views.py`;
- `models.py`;
- `utils.py`;
- `settings.py`;
- `tests.py`;
sean coherentes con el estado actual.

Agregar `models.py` y `utils.py` a archivos importantes si todavía no están descritos.

## 6. LIMPIAR `## 6. ERRORES ACTUALES`

No listar como pendientes acciones que ya fueron ejecutadas.

Debe quedar solo:

- **Bloqueantes funcionales actuales: ninguno conocido.**
- **Pendientes técnicos para revisión: ninguno crítico.**
- SQLite continúa como entorno de desarrollo.
- PostgreSQL/MySQL: recordatorio académico futuro.
- Fase documental: pendiente de autorización del usuario.
- módulos huéspedes/cabañas/desayuno/ofertas: congelados y fuera del núcleo evaluable.

Si durante esta limpieza aparece un problema real reproducible, registrarlo con:
- archivo;
- línea/función;
- pasos para reproducir;
- severidad;
- solución aplicada o pendiente.

## 7. LIMPIAR `## 10. SIGUIENTE TAREA`

Reemplazar cualquier lista de trabajo ya realizada por:

- **Siguiente tarea: ninguna de desarrollo.**
- Proyecto congelado para revisión y retroalimentación.
- Esperar nueva instrucción del usuario o feedback del docente/equipo.
- No modificar código funcional sin error reproducible o nueva autorización.

## 8. LIMPIAR `## 12. REGLAS PERMANENTES`

Eliminar o marcar como históricas reglas contradictorias como:

- “seguir el Plan Maestro RF07–RF18”;
- “cada RF restante debe implementarse”;
- “prioridad Entrega 3” si aparece como prioridad vigente.

Dejar estas reglas vigentes:

1. RF01–RF18 permanecen cerrados salvo regresión reproducible.
2. RF19–RF24 permanecen excluidos.
3. No agregar nuevas funcionalidades antes de revisión.
4. Suite vigente: 220/220; conteos menores son históricos.
5. prioridad vigente: revisión y retroalimentación.
6. módulos huéspedes/cabañas/desayuno/ofertas congelados.
7. no modificar Word, Draw.io ni informe sin autorización expresa.
8. recordatorios académicos se conservan pero no gobiernan trabajo actual.
9. leer y actualizar `AI_CONTEXT.md` solo ante cambios relevantes.
10. no inventar resultados, métricas, rutas, pruebas ni requisitos.

## 9. PRESERVAR RECORDATORIOS DE EVALUACIÓN

No borrar ni ejecutar ahora:

- retroalimentación del Informe 2;
- PostgreSQL/MySQL;
- modelo lógico/físico;
- Azure DevOps;
- redacción impersonal;
- plantilla de pares;
- documentación de performance;
- Entrega 3.

Mantener todos estos bloques bajo el encabezado:

**RECORDATORIO ACADÉMICO / NO PRIORIDAD ACTUAL**

El usuario decidirá cuándo trabajar cada punto.

## 10. VERIFICACIÓN FINAL DEL PROYECTO

Después de limpiar el contexto, ejecutar únicamente:

1. `python manage.py check`
2. `python manage.py test ventas`
3. `python manage.py showmigrations`
4. regresión básica de los 4 roles
5. `git status`

No modificar comportamiento funcional salvo que una de estas verificaciones encuentre una regresión real.

Registrar:
- conteo exacto de tests;
- errores/fallos;
- migraciones pendientes si existen;
- estado Git;
- cualquier archivo modificado durante la limpieza.

## 11. CHECKLIST FINAL QUE DEBE QUEDAR EN EL AI_CONTEXT

Crear o actualizar:

`## CHECKLIST FINAL PRE-REVISIÓN`

Debe ser corto y contener:

- [ ] RF01–RF18 cerrados
- [ ] 220/220 pruebas o nuevo conteo exacto
- [ ] check limpio
- [ ] migraciones al día
- [ ] 4 roles verificados
- [ ] SQLite identificado
- [ ] 25 modelos auditados
- [ ] mocks evaluables eliminados
- [ ] `.env` protegido
- [ ] `db.sqlite3` fuera de Git
- [ ] benchmark real registrado
- [ ] ninguna orden antigua activa
- [ ] ninguna función nueva agregada
- [ ] ningún bloqueante funcional conocido

Marcar con `[x]` solo aquello comprobado.

## 12. CRITERIO DE CIERRE

La tarea termina cuando:

- `AI_CONTEXT.md` quedó con todas sus órdenes anteriores marcadas como históricas;
- no hay contradicciones entre estado actual e historial;
- no quedan órdenes antiguas que parezcan activas;
- RF09 permanece 127/127 histórico;
- matriz RF07/RF10 permanece corregida;
- `check` y suite siguen en verde;
- Git está limpio o cualquier cambio pendiente está documentado;
- checklist pre-revisión está completo.

Después:

**STOP DESARROLLO.**

No tocar:
- RF;
- modelos;
- vistas;
- templates;
- base de datos;
- informe;
- Word;
- Draw.io;

salvo nueva instrucción del usuario o regresión reproducible.

---

# HISTÓRICO — ORDEN DE PREPARACIÓN PARA REVISIÓN YA EJECUTADA / NO VIGENTE

> [!IMPORTANT]
> Esta fue una orden vigente en una fase anterior. Se conserva únicamente como trazabilidad histórica y NO debe ejecutarse. Su objetivo fue dejar el proyecto limpio, estable y preparado para revisión.

## FASE 1 — LIMPIEZA Y COHERENCIA DEL AI_CONTEXT

1. Corregir el encabezado de RF09:
   - reemplazar `125/125` por **127/127**, que coincide con el cierre real del propio bloque.
2. Marcar el bloque `PLAN MAESTRO RF07–RF18 — ORDEN COMPLETO DE INICIO A FIN` como:
   - **HISTÓRICO — PLAN YA EJECUTADO / NO ES ORDEN VIGENTE**.
3. Marcar cualquier instrucción antigua del tipo:
   - “detener antes de RF08”;
   - “siguiente paso RF07”;
   - “RF05 pendiente”;
   - “Semana 10/11 prioridad”;
   como **histórico/no vigente** cuando aún aparezca.
4. Mantener el estado vigente global:
   - RF01–RF18 completos;
   - 220/220 pruebas;
   - 0 incidencias en `check`.
5. Mantener los conteos anteriores de pruebas solo como historial cronológico.
6. No borrar evidencia histórica útil, pero impedir que pueda confundirse con el estado actual.

## FASE 2 — CORRECCIÓN DE MATRIZ DE EVIDENCIAS

Corregir textos que se alejan del alcance oficial:

1. RF07:
   - reemplazar expresiones centradas en `huésped`, `cabaña` o `desayuno`;
   - usar **Convenio / Beneficio Autorizado / Precio Especial**.
   - evidencia sugerida: aplicación de convenio o valor especial autorizado + trazabilidad.
2. RF10:
   - eliminar frases que sugieran que el consumo interno se “descuenta en caja” como una venta normal;
   - describirlo como:
     - registro de consumo interno;
     - saldo acumulado del trabajador;
     - historial;
     - liquidación/descuento posterior por planilla cuando corresponda.
3. Revisar RF01–RF18 completos y corregir cualquier evidencia sugerida que:
   - no exista realmente;
   - mezcle módulos extras;
   - contradiga la implementación vigente.
4. No inventar nombres de tests, rutas o funciones. Si un dato no puede comprobarse, marcarlo para revisión.

## FASE 3 — HIGIENE DEL REPOSITORIO

### 3.1 `db.sqlite3`
- HISTÓRICO — brecha registrada en esa fecha; resuelta posteriormente: `db.sqlite3` fue retirado del índice Git (`git rm --cached`) y agregado a `.gitignore`, preservando la base de datos física localmente.
- Procedimiento ejecutado:
  1. agregar `db.sqlite3` a `.gitignore` si no está;
  2. ejecutar `git rm --cached db.sqlite3`;
  3. confirmar que el archivo local físico NO se elimine;
  4. verificar con `git status`;
  5. no borrar datos locales.
- Registrar el resultado exacto en `AI_CONTEXT.md`.

### 3.2 Secretos
- Confirmar:
  - `.env` ignorado;
  - `.env.example` presente;
  - `SECRET_KEY` cargada desde variables de entorno;
  - ningún secreto real rastreado por Git.
- No publicar valores reales dentro de `AI_CONTEXT.md`.

### 3.3 Archivos temporales
- Auditar el repositorio por:
  - `__pycache__`;
  - `.pyc`;
  - logs;
  - ZIPs;
  - copias antiguas;
  - temporales;
  - bases de datos de prueba.
- No borrar versiones históricas expresamente conservadas por el usuario; solo confirmar que estén correctamente excluidas del repositorio principal cuando corresponda.

## FASE 4 — AUDITORÍA DE CÓDIGO Y DATOS SIN CAMBIAR FUNCIONALIDAD

Revisar y corregir únicamente problemas seguros y reproducibles:

1. imports no usados;
2. funciones muertas/deprecadas;
3. rutas duplicadas;
4. consultas ORM claramente redundantes;
5. variables o comentarios obsoletos;
6. referencias a mocks antiguos;
7. `localStorage` antiguo que ya no participe del flujo vigente;
8. hardcodes residuales en flujos evaluables;
9. mensajes técnicos expuestos al usuario;
10. inconsistencias de nombres entre Cajero/Vendedor, Mesero/Salón, Cocina/KDS y Barra/BDS/KDS.
11. verificar que los datos principales provengan de BD:
    - ventas;
    - detalles;
    - pedidos;
    - tickets;
    - entregas;
    - mesas;
    - consumos internos;
    - reportes.
12. no hacer refactor amplio si la mejora no es necesaria para estabilidad o claridad.

## FASE 5 — AUDITORÍA FUNCIONAL DE REGRESIÓN

Ejecutar nuevamente:

1. `python manage.py check`
2. `python manage.py test ventas`
3. `python manage.py showmigrations`

Luego validar manualmente:

### ADMINISTRADOR
- login;
- dashboard;
- locales;
- trabajadores;
- mesas;
- productos;
- menús;
- historial;
- reportes.

### CAJERO
- login;
- jornada;
- caja;
- venta rápida;
- venta en mesa si corresponde;
- precio especial;
- ticket/comprobante;
- consumo interno.

### MESERO
- login;
- mesas;
- cuenta abierta;
- múltiples rondas;
- notas por producto;
- reasignación de mesa;
- cierre/cobro;
- entrega.

### COCINERO / KDS
- pedidos entrantes;
- transición de estados;
- aislamiento Cocina/Barra;
- notas;
- marcado LISTO;
- comunicación con salón.

Registrar cada resultado como:
- `[OK]`
- `[CORREGIDO]`
- `[PENDIENTE]`
- `[NO APLICA]`

## FASE 6 — CASOS CRÍTICOS QUE DEBEN QUEDAR VERIFICADOS

Verificar que el sistema se comporte correctamente ante:

1. doble clic;
2. doble POST;
3. usuario sin permiso;
4. sesión expirada;
5. ID inexistente;
6. producto inactivo;
7. mesa ocupada;
8. mesa inactiva;
9. traslado de mesa a otro local;
10. venta con precio manipulado desde navegador;
11. precio especial inválido;
12. pedido vacío;
13. ticket vacío;
14. impresora en fallo;
15. reimpresión;
16. entrega duplicada;
17. entrega antes de LISTO;
18. consumo interno duplicado;
19. cierre de mesa con cuenta abierta;
20. dos usuarios actuando sobre la misma mesa/venta;
21. cambio de día/jornada;
22. reportes sin datos;
23. rango de fechas inválido;
24. producto histórico desactivado;
25. error de BD o excepción durante una transacción atómica.

No crear funciones nuevas para estos casos si ya están cubiertos; solo comprobar y corregir regresiones reales.

## FASE 7 — BASE DE DATOS

- Mantener **SQLite como motor activo de desarrollo** durante esta preparación para revisión.
- NO migrar a PostgreSQL/MySQL ahora si eso puede introducir riesgo.
- Mantener preparada la configuración externa existente mediante variables de entorno.
- El recordatorio académico sobre PostgreSQL/MySQL queda conservado para una fase posterior decidida por el usuario.
- No afirmar que PostgreSQL está activo si no lo está.

## FASE 8 — RENDIMIENTO

- Conservar como resultado real vigente:
  - 20 usuarios concurrentes;
  - 100 peticiones;
  - 100% éxito;
  - 162.72 RPS;
  - promedio 77.69 ms;
  - P95 535.43 ms.
- No inventar datos de 50/100 usuarios.
- Si el script de benchmark puede ejecutarse nuevamente sin riesgo:
  - repetirlo una vez como regresión;
  - comparar resultados;
  - registrar el nuevo resultado.
- No hacer optimizaciones especulativas si el rendimiento actual es correcto.

## FASE 9 — PREPARACIÓN PARA REVISIÓN

Crear dentro del `AI_CONTEXT.md` una sección breve llamada:

`## CHECKLIST FINAL PRE-REVISIÓN`

Debe contener:
- estado RF01–RF18;
- suite exacta;
- migraciones;
- motor BD;
- 4 roles;
- 25 modelos;
- seguridad;
- repositorio limpio;
- mocks;
- rendimiento;
- pendientes reales, si quedan.

Debe ser corta, clara y servir para que el equipo/docente pueda entender el estado actual rápidamente.

## FASE 10 — RECORDATORIOS ACADÉMICOS

- Mantener intactos los bloques de:
  - retroalimentación del Informe 2;
  - PostgreSQL/MySQL;
  - modelo lógico/físico;
  - Azure DevOps;
  - redacción impersonal;
  - plantilla de pares;
  - pruebas de rendimiento para informe;
  - Entrega 3.
- Marcar esos bloques como:
  - **RECORDATORIO PARA FASE DOCUMENTAL / NO PRIORIDAD ACTUAL**.
- No ejecutarlos ni modificar documentos académicos todavía.

## CRITERIO DE CIERRE

Antes de detenerse, Antigravity debe devolver:

1. `AI_CONTEXT.md` reconciliado y coherente.
2. RF09 corregido a 127/127.
3. Plan Maestro antiguo marcado como histórico.
4. Matriz RF07/RF10 corregida.
5. `db.sqlite3` fuera del índice de Git, pero conservado localmente.
6. `.env` protegido y secretos fuera de Git.
7. `python manage.py check` limpio.
8. suite completa en verde con conteo exacto.
9. migraciones confirmadas.
10. regresión manual de 4 roles.
11. lista de cualquier problema real detectado/corregido.
12. checklist final para revisión.
13. ningún cambio en Word/Draw.io/informe.
14. ningún RF nuevo.
15. detener y devolver el archivo para revisión de ChatGPT/usuario.

---

# INFORME DE RESULTADOS DE LA CONSOLIDACIÓN FINAL (01/11/2026)

### 1. Estado Técnico Verificado
- **Chequeo del Sistema (`python manage.py check`)**: **0 incidencias** (0 silenced).
- **Suite Oficial de Pruebas (`python manage.py test ventas`)**: **220 / 220 pruebas aprobadas (100% OK en 388.5s)**. Cero fallos, cero errores.
- **Migraciones de Base de Datos (`python manage.py showmigrations`)**:
  - `ventas`: 20 migraciones aplicadas al 100% (`0001_initial` hasta `0020_mesa_fecha_ocupacion`).
  - `auth`: 12 migraciones aplicadas.
  - `admin`: 3 migraciones aplicadas.
  - `contenttypes`: 2 migraciones aplicadas.
  - `sessions`: 1 migración aplicada.
- **Motor de Base de Datos Activo**: `django.db.backends.sqlite3` (`db.sqlite3`).
  - *Dictamen*: Entorno de desarrollo local opera sobre SQLite. Variables preparadas en `.env` para PostgreSQL si se requiere en despliegue. No se declara falsamente PostgreSQL como activo.
- **Seguridad y Variables de Entorno**:
  - `SECRET_KEY`: Cargada dinámicamente desde `.env` vía `load_dotenv` con fallback de desarrollo.
  - `DEBUG`: `True` en entorno de desarrollo local.
  - Archivo `.env`: Existente en raíz, ignorado por `.gitignore`, **nunca commiteado en el historial de Git**.
  - Archivo `.env.example`: Disponible con plantilla de variables.
  - Archivo `db.sqlite3`: **Desvinculado exitosamente del seguimiento de Git** mediante `git rm --cached db.sqlite3` y protegido en `.gitignore`. El archivo físico local se mantiene intacto y plenamente operativo.
- **Mocks y Datos Simulados**: **0% mocks**. Erradicación total en RF18 y en todos los controladores; gráficos, KPIs y reportes operan 100% sobre ORM real.
- **Control de Acceso y Roles (RBAC)**: Verificado al 100% en `scratch/verificar_rf18.py` para los 4 roles (Administrador, Cajero, Mesero, Cocina).

### 2. Clasificación Oficial de Hallazgos
- `[OK]` Check de Django con 0 incidencias.
- `[OK]` Suite completa de 220 pruebas aprobada.
- `[OK]` Todas las 20 migraciones de la app `ventas` aplicadas.
- `[OK]` Erradicación total de mocks en dashboard analítico y reportes descargables.
- `[OK]` Control de concurrencia y bloqueo de fila (`select_for_update`) en caja, comandas y reasignación.
- `[OK]` Script anti doble envío en botones críticos.
- `[OK]` Políticas de seguridad de contraseñas (cero texto plano, hashing PBKDF2/SHA-256, cambio obligatorio al primer login).
- `[OK]` Aislamiento estricto de roles (RBAC) y bloqueo de rutas no autorizadas.
- `[OK / CORREGIDO]` Archivo `db.sqlite3` desvinculado del índice de Git (commit `4e8d544`) y protegido en `.gitignore`; base de datos física local preservada intacta.
- `[PENDIENTE]` Despliegue en motor relacional externo (PostgreSQL) si el docente exige evidencia de motor cliente-servidor para Entrega 3.

### 3. Modelo de Datos Real — 25 Entidades / Tablas en `ventas`
El modelo de datos actual consta de **25 modelos** (superando las 19 entidades iniciales tras la incorporación de los RF05–RF18 y los módulos de soporte):

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

### 4. Pruebas de Rendimiento Reales (Benchmark Empírico)
Ejecutadas con `scratch/benchmark_rendimiento.py` sobre el servidor de desarrollo activo (`http://127.0.0.1:8000/`) con **20 usuarios concurrentes simultáneos (100 peticiones HTTP)**:
- **Corrida 1 (Línea Base)**:
  - Rendimiento: **162.72 RPS**.
  - Latencia promedio: **77.69 ms** (mediana: 21.08 ms, P95: 535.43 ms).
  - Tasa de éxito: **100.0%** (100/100 HTTP 200).
- **Corrida 2 (Regresión de Verificación FASE 8)**:
  - Rendimiento: **166.59 RPS**.
  - Latencia promedio: **70.84 ms** (mediana: 16.03 ms, P95: 524.29 ms).
  - Tasa de éxito: **100.0%** (100/100 HTTP 200).
  - Latencia mínima / máxima: 1.09 ms / 535.48 ms.
- *Nota formal*: Únicamente se reportan datos medidos empíricamente sobre el entorno actual. No se fabrican cifras para 50 o 100 usuarios.

### 5. Matriz de Evidencias Técnicas RF01–RF18 para Entrega 3

| Requerimiento | Nombre Oficial | Estado | Ruta / Vista Principal | Modelos Django Involucrados | Pruebas Automatizadas Representativas | Evidencia Sugerida para Informe |
| :--- | :--- | :---: | :--- | :--- | :--- | :--- |
| **RF01** | Gestión de Usuarios y Roles | **100% OK** | `/administrador/trabajadores/`, `/login/` | `User`, `PerfilEmpleado`, `PuntoVenta` | `SafariUsuariosRolesTests`, `SafariRF01` | Captura CRUD trabajadores, cambio forzoso de clave, checklist visual reactivo. |
| **RF02** | Apertura y Cierre de Jornada | **100% OK** | `/administrador/`, `/abrir-jornada/` | `Jornada`, `User` | `SafariJornadaTests` | Captura modal apertura jornada con fecha de hoy y bloqueo de reutilización de ayer. |
| **RF03** | Apertura y Arqueo de Caja Individual | **100% OK** | `/cajero/`, `/abrir-caja/`, `/cerrar-caja/` | `Caja`, `Jornada`, `User`, `PuntoVenta` | `SafariCajaTests`, `SafariArqueoTests` | Captura formulario apertura con fondo opcional ($0) y arqueo detallado con billetes. |
| **RF04** | Gestión de Mesas por Local | **100% OK** | `/administrador/mesas/`, `/salon/` | `Mesa`, `PuntoVenta` | `SafariMesasCRUDTests` | Captura listado de mesas por local, estados Libre/Ocupada/Inactiva. |
| **RF05** | Reasignación de Mesas | **100% OK** | `/salon/` (`reasignar_mesa`) | `ReasignacionMesa`, `Mesa`, `Venta` | `SafariRF05ReasignacionMesasTests` (9 tests) | Captura modal traslado de mesa, traspaso de comanda y log en historial admin. |
| **RF06** | Registro de Ventas y Cobro POS | **100% OK** | `/vendedor/` (`crear_ticket`) | `Venta`, `DetalleVenta`, `Caja` | `SafariVentaPOSTests` | Captura pantalla POS con carro de compras, cálculo de IVA y redondeo Ley 20.956. |
| **RF07** | Gestión de Precios Especiales y Convenios | **100% OK** | `/vendedor/`, `/administrador/convenios/`| `PrecioEspecial`, `RegistroPrecioEspecial`, `DetalleVenta` | `SafariRF07GestionPreciosVentaTests` (14 tests) | Captura de aplicación de Convenio / Beneficio Autorizado o Precio Especial, mostrando el valor aplicado y su trazabilidad en auditoría. |
| **RF08** | Generación de Tickets con Código Único | **100% OK** | `/ticket/<id>/imprimir/` | `Ticket`, `Venta`, `Pedido` | `SafariRF08GeneracionTicketsTests` (9 tests) | Captura ticket térmico digital con QR, desglose CLP y marca de reimpresión. |
| **RF09** | Gestión de Impresión Descentralizada | **100% OK** | `/kds-barra/`, `/cocina/` | `PuntoImpresion`, `RegistroImpresion`, `Ticket` | `SafariRF09GestionImpresionKdsBarraTests` (11 tests)| Captura despacho separado de comanda Cocina vs Barra KDS con alertas visuales. |
| **RF10** | Consumo Interno / Fiado | **100% OK** | `/vendedor/consumo-interno/` | `ConsumoInterno`, `DetalleConsumoInterno`, `Caja` | `SafariRF10ConsumoInternoFiadoTests` (10 tests) | Captura de registro de consumo interno, saldo acumulado por trabajador, historial y liquidación posterior por planilla cuando corresponda. |
| **RF11** | Asignación de Mesa o Venta Rápida | **100% OK** | `/vendedor/crear-ticket/` | `Venta`, `Mesa`, `PuntoVenta` | `SafariRF11ModalidadVentaMesaRapidaTests` (8 tests) | Captura conmutador de modalidades Mesa / Venta Rápida / Llevar en POS y Mesero. |
| **RF12** | Comentarios Asociados a Productos | **100% OK** | `/vendedor/`, `/salon/`, `/cocina/` | `DetalleVenta`, `DetallePedido`, `Pedido` | `SafariRF12ComentariosProductosTests` (8 tests) | Captura de notas libres ("sin cebolla", "bien cocido") reflejadas en comandas KDS. |
| **RF13** | Registro de Entrega de Productos | **100% OK** | `/cocina/` (`confirmar_entrega`) | `Entrega`, `Pedido`, `Ticket`, `User` | `SafariRF13RegistroEntregaProductosTests` (8 tests)| Captura botón de despacho comensal, registro del colaborador que entrega y hora exacta. |
| **RF14** | Gestión de Puntos de Venta (Locales) | **100% OK** | `/administrador/`, `/administrador/local/<id>/` | `PuntoVenta`, `AlertaTraslado`, `PerfilEmpleado` | `SafariRF14PuntosVentaLocalesTests` (11 tests)| Captura CRUD locales gastronómicos, métricas individuales y alertas de traslado. |
| **RF15** | Posicionamiento de Menús por Local | **100% OK** | `/administrador/menus/`, `/vendedor/` | `Menu`, `Producto`, `Categoria`, `PuntoVenta` | `SafariRF15PosicionamientoProductosMenusTests` (13 tests)| Captura cartas gastronómicas diferenciadas por local con precios específicos. |
| **RF16** | Control de Tiempos de Atención | **100% OK** | `/administrador/historial/`, `/administrador/local/<id>/` | `Pedido`, `Entrega`, `Venta` | `SafariRF16ControlTiemposAtencionTests` (12 tests) | Captura tarjetas de tiempo de espera comensal, tiempo en cola y tiempo de cocción KDS. |
| **RF17** | Gestión de Ocupación de Mesas | **100% OK** | `/salon/`, `/administrador/mesas/` | `Mesa`, `Venta`, `PuntoVenta` | `SafariRF17GestionOcupacionMesasTests` (10 tests) | Captura cronómetro comensal en vivo, bloqueo de liberación indebida y tasa de rotación. |
| **RF18** | Reportes y Estadísticas Consolidadas | **100% OK** | `/administrador/dashboard/`, `/exportar-ventas/` | `Venta`, `DetalleVenta`, `Pedido`, `Mesa` | `SafariRF18ReportesEstadisticasTests` (13 tests) | Captura dashboard con cero mocks, filtros por fecha/local, Top 10 y exportación Excel/Word.|

---

### PLAN MAESTRO RF07–RF18 — HISTÓRICO / PLAN YA EJECUTADO

> [!CAUTION]
> Todo texto imperativo, secuencia de implementación, “detener”, “no iniciar RF siguiente” o instrucción contenida en este bloque corresponde únicamente al historial de desarrollo. **NO constituye una orden activa.**

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

# RF09 — GESTIÓN DE IMPRESIÓN — [ESTADO: COMPLETADO Y CERRADO (127/127 OK)]

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

# RF10 — CONSUMO INTERNO DEL PERSONAL / FIADO — [ESTADO: COMPLETADO Y CERRADO (137/137 OK)]

### Resumen de Cierre y Verificación Oficial (RF10)
- **Fecha de Cierre:** 2026-11-01
- **Migración Aplicada:** `0017_consumointerno_caja_consumointerno_descontado_por_and_more.py`
- **Modelos Actualizados (`ventas/models.py`):**
  * `ConsumoInterno`: campos añadidos `tipo_consumo` (`FIADO`, `COLACION`, `CORTESIA`), `registrado_por` (User FK), `caja` (Caja FK), `descontado_por` (User FK), `fecha_hora_descuento`. Método `recalcular_total()` para asegurar coherencia financiera.
  * `PerfilEmpleado`: método `total_fiado_pendiente()` para cálculo acumulado en tiempo real de deuda por nómina (RF10.3).
  * `ConsumoInternoAdmin` (`ventas/admin.py`): filtros avanzados por tipo, estado, punto de venta y fechas.
- **Capa y Servicio Lógico Financiero (`ventas/utils.py`):**
  * `registrar_consumo_interno`: transacción atómica completa (`with transaction.atomic()`), validación estricta de colaborador activo (RF10.1), obtención de precios unitarios estrictamente desde `Producto.precio_base` en la BD (RF10.2) protegiendo contra manipulación de precios desde el cliente o navegador, rechazo de cantidades <= 0 y productos inactivos.
  * **Regla de Oro Contable (RF10.4):** Separación absoluta entre ventas a clientes y consumos del personal. `ConsumoInterno` **nunca crea registros en `Venta` ni `DetalleVenta`** y **nunca infla el total recaudado ni arqueo de caja** (`caja.total_recaudado` permanece intacto).
  * `liquidar_consumos_por_planilla`: servicio de liquidación en lote o individual que transiciona estados a `DESCONTADO` y estampa al supervisor y marca de tiempo (RF10.3).
- **Vistas, Endpoints y Plantillas:**
  * Modal POS en `vendedor_crear_ticket.html`: botón dedicado `#btnConsumoInterno` y modal `#modalConsumoInterno` con dropdown de `trabajadores_activos` (nombre, rol y local), tipos de consumo, observaciones, y confirmación asíncrona vía AJAX.
  * Endpoint POS: `registrar_consumo_interno_view` (`/consumo-interno/registrar/`) con respuesta JSON/HTTP y control de roles (`ADMINISTRADOR`, `CAJERO`).
  * Panel Administrativo: `administrador_consumos` (`/administrador/consumos/`, `administrador_consumos.html`) con KPIs (fiado pendiente, total liquidado, colaboradores con deuda), tabla de saldos por colaborador con botón directo de liquidación por nómina, historial filtrable y opciones de anulación.
  * Trazabilidad en Bitácora: integración de eventos tipo `CONSUMO_INTERNO` en `administrador_historial` con badges y montos.
  * Menú de Navegación: enlace directo integrado en `administrador.html`.
- **Resultados de Pruebas Automatizadas:**
  * Tests específicos RF10 (`SafariRF10ConsumoInternoTests`): 10/10 tests OK.
  * Suite completa (`python manage.py test ventas`): **137/137 tests pasados exitosamente en 281.2s (0 fallos, 0 errores)**.
  * `python manage.py check`: 0 issues.
- **Regresión Manual de 4 Roles:**
  * Administrador (`rgomez`): 200 OK.
  * Cajero (`cvalenzuela`): 200 OK.
  * Mesero (`dsilva`): 200 OK.
  * Cocinero (`eparedes`): 200 OK.
  * RF05 (Reasignación de Mesas): intacto y verificado.

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

# RF11 — ASIGNACIÓN DE MESA O VENTA RÁPIDA — [ESTADO: COMPLETADO Y CERRADO (145/145 OK)]

### Resumen de Cierre y Verificación Oficial (RF11)
- **Modelos y Normalización:**
  * `Venta.modalidad`: opciones formales `VENTA_RAPIDA` ("Venta Rápida / Retiro en Mostrador"), `MOSTRADOR` (alias) y `MESA` ("Consumo en Mesa (Salón)").
  * Validación centralizada en `Venta.clean()` y `validar_modalidad_operativa`:
    - Modalidad `MESA` exige estrictamente `mesa` no nula, perteneciente al mismo `PuntoVenta` de la transacción.
    - Prevención de colisión de cuentas abiertas: rechazo inmediato si otra venta abierta ya se encuentra asignada a dicha mesa.
    - Modalidad `VENTA_RAPIDA`: desacopla cualquier mesa física asignada (`self.mesa = None`), normaliza alias (`MOSTRADOR`, `LLEVAR`, `RETIRO`), y garantiza que las mesas físicas del local permanezcan intactas en su estado (`HABILITADA`).
    - Métodos de conveniencia añadidos al modelo `Venta`: `es_consumo_en_mesa()`, `es_venta_rapida()` y `get_ubicacion_despacho()`.
- **Integración de Vistas y Plantillas:**
  * POS Cajero (`crear_ticket` / `vendedor_crear_ticket.html`): incorporación de selector de modalidad visual interactivo (Venta Rápida / Mostrador vs. Consumo en Mesa) con selector dinámico de mesas disponibles (`mesas_disponibles`).
  * Validación server-side ante intentos de cobrar en mesa sin selección (HTTP 400 JsonResponse).
  * Salón Mesero (`mesero`): validación estricta de mesa requerida y pertenencia al punto de venta para comanda inicial y multi-ronda. Cobro y cierre mediante `cerrar_cuenta_mesa` liberando la mesa a `HABILITADA`.
  * Comandas KDS y Digital Tickets (`generar_contenido_ticket_cocina` / `generar_contenido_ticket_barra`): soporte completo para artículos calientes de cocina y preparados de barra en venta rápida, imprimiendo/visualizando el aviso claro "Retiro Rápido / Mostrador".
- **Pruebas Automatizadas y Calidad:**
  * Tests específicos RF11 (`SafariRF11AsignacionMesaVentaRapidaTests`): 8/8 tests OK.
  * Suite completa del sistema: 145/145 tests OK (0 fallos, 0 errores).
  * System check `py manage.py check`: 0 incidencias.
  * Verificación manual de los 4 roles (Administrador, Cajero, Mesero, Cocinero): 100% verificado.

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

# RF12 — COMENTARIOS ASOCIADOS A PRODUCTOS — [ESTADO: COMPLETADO Y CERRADO (153/153 OK)]

### Resumen de Cierre y Verificación Oficial (RF12)
- **Sanitización Robusta (OWASP ASVS):**
  * Función `sanitizar_observacion(texto, max_length=200)` en `ventas/utils.py`:
    - Elimina espacios en blanco superfluos con `strip()`.
    - Normaliza textos vacíos o conformados exclusivamente por espacios o caracteres nulos (`\x00`) a `None`.
    - Neutraliza completamente ataques XSS mediante `html.escape(texto_str)`.
    - Trunca de forma segura a longitud máxima de 200 caracteres, respetando tildes y caracteres especiales del idioma español.
  * Modelo `DetallePedido` (`ventas/models.py`):
    - Implementación de `clean()` y `save()` que ejecutan automáticamente `sanitizar_observacion`, garantizando que cualquier registro creado o modificado sea sanitizado sin excepciones a nivel de base de datos.
- **Aislamiento Estricto y Trazabilidad Multi-ronda:**
  * Cada producto mantiene su propia nota sin filtraciones ni cruce de comentarios entre ítems del mismo pedido.
  * En salón con comanda multi-ronda, cada ronda genera un `Pedido` independiente; la ronda 2 no sobreescribe ni hereda notas obsoletas de la ronda 1.
  * En frontend, reinicio de estados de notas (`notasProductos`, `notasProductosCajero`) tras el despacho para prevenir contaminación en rondas o ventas posteriores.
- **Tickets e Impresión / KDS Cocina y BDS Barra:**
  * `generar_contenido_ticket_cocina` y `generar_contenido_ticket_barra`: formato térmico estructurado con etiqueta `Nota: ...` y ajuste limpio de ancho.
  * `reimprimir_ticket`: preserva íntegramente las observaciones individuales históricas de la comanda junto con el banner de reimpresión.
  * Pantallas táctiles de Cocina (`cocina.html`) y Barra (`barra.html`): renderizado visual seguro de las notas de comanda con badge de advertencia.
- **Pruebas Automatizadas y Calidad:**
  * Tests específicos RF12 (`SafariRF12ComentariosProductosTests`): 8/8 tests OK.
  * Suite completa del sistema: 153/153 tests OK (0 fallos, 0 errores).
  * System check `py manage.py check`: 0 incidencias.
  * Verificación manual de los 4 roles (Administrador, Cajero, Mesero, Cocinero): 100% verificado.

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

# RF13 — REGISTRO DE ENTREGA DE PRODUCTOS — [ESTADO: COMPLETADO Y CERRADO (161/161 OK)]

### Resumen de Cierre y Verificación Oficial (RF13)
- **Fecha de Cierre:** 2026-11-01
- **Migración Aplicada:** `0019_pedido_fecha_inicio_preparacion_pedido_fecha_listo.py`
- **Modelos Actualizados (`ventas/models.py`):**
  * `Pedido`: incorporación de marcas de tiempo operativas `fecha_inicio_preparacion` y `fecha_listo`. Métodos de cálculo de tiempos `get_tiempo_preparacion_minutos()` y `get_tiempo_espera_total_minutos()`.
  * `Entrega`: validaciones integradas en `clean()` y `save()` que blindan a nivel de modelo que solo comandas en estado `LISTO` puedan entregarse, prohibiendo terminantemente entregas de pedidos `CANCELADOS` y duplicación de entregas (RF13.4). Métodos de conveniencia añadidos: `get_ubicacion()`, `get_punto_venta()`, `get_tiempo_desde_creacion_minutos()` y `get_tiempo_desde_creacion_segundos()`.
- **Servicios y Lógica Operativa (`ventas/utils.py`):**
  * `validar_transicion_estado_pedido()`: máquina de estados rigurosa `PENDIENTE` -> `EN_PREPARACION` -> `LISTO` -> `ENTREGADO`. Estados terminales inmutables (`ENTREGADO`, `CANCELADO`).
  * `registrar_entrega_pedido()`: servicio atómico con bloqueo de concurrencia `select_for_update()`, verificación de estado `LISTO`, sanitización de observaciones (OWASP ASVS), asignación de usuario responsable (`usuario_entrega`), vinculación a ticket y cierre automático de tickets asociados a `FINALIZADO`.
- **Integración de Vistas y Plantillas:**
  * Endpoint KDS/BDS/Salón (`cambiar_estado_pedido` en `ventas/views.py`): operación bajo `transaction.atomic()` y `select_for_update()`, delegación de entrega a `registrar_entrega_pedido`, captura estructurada de `ValidationError` y respuestas HTTP 400 coherentes para llamadas AJAX/KDS y redirección segura para salón.
  * Salón Mesero (`mesero.html`): notificación visual de comandas listas para servir y botón "Servir" que marca la entrega manteniendo la mesa ocupada mientras la cuenta siga abierta.
  * Auditoría Administrativa (`administrador_historial`): trazabilidad de eventos `ENT-...` con ubicación ("Mesa X (Salón)" vs "Retiro Rápido / Mostrador") y tiempos de atención reales en minutos.
- **Pruebas Automatizadas y Calidad:**
  * Tests específicos RF13 (`SafariRF13RegistroEntregaProductosTests`): 8/8 tests OK.
  * Suite completa del sistema: 161/161 tests OK en 278.8s (0 fallos, 0 errores).
  * System check `py manage.py check`: 0 incidencias.
  * Verificación manual de los 4 roles (Administrador, Cajero, Mesero, Cocinero): 100% verificado.

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

# RF14 — GESTIÓN DE PUNTOS DE VENTA — [ESTADO: COMPLETADO Y CERRADO (172/172 OK)]

### Resumen de Cierre y Verificación Oficial (RF14)
- **Fecha de Cierre:** 2026-11-01
- **Modelos y Métodos Operativos (`ventas/models.py`):**
  * `PuntoVenta`: incorporación de métodos de control de integridad operativa: `tiene_cajas_abiertas()`, `tiene_ventas_abiertas()` y `tiene_historial_operativo()`.
- **Lógica de Protección y Vistas (`ventas/views.py`):**
  * `crear_local`: validación rigurosa de nombre no vacío, unicidad case-insensitive, soporte AJAX estructurado y creación con estado activo por defecto.
  * `modificar_local`: validación de nombre y unicidad excluyendo el propio ID; blindaje estricto que prohíbe desactivar (`activo=False`) si el local tiene cajas abiertas o cuentas en consumo activas en salón (`RF14`).
  * `eliminar_local`: blindaje contra eliminación con cajas o ventas abiertas; soft-delete obligatorio (`activo=False`) ante presencia de historial operativo (ventas, cajas, consumos de colaboradores o mesas con auditoría) para proteger la integridad histórica; eliminación física limpia solo si el local no posee transacciones históricas; desasignación automática y segura de trabajadores (`punto_venta_actual=None`) sin eliminar perfiles de usuario.
  * `administrador_local`: blindaje mediante decorador `@requiere_rol(['ADMINISTRADOR'])` y respuesta controlada HTTP 404 ante identificadores inexistentes.
- **Pruebas Automatizadas y Calidad:**
  * Tests específicos RF14 (`SafariRF14GestionPuntosVentaTests`): 11/11 tests OK.
  * Suite completa del sistema: 172/172 tests pasados exitosamente en 337.1s (0 fallos, 0 errores).
  * System check `py manage.py check`: 0 incidencias.
  * Verificación manual de los 4 roles (Administrador, Cajero, Mesero, Cocinero): 100% verificado.

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

# RF15 — POSICIONAMIENTO DE PRODUCTOS Y MENÚS — [ESTADO: COMPLETADO Y CERRADO (185/185 OK)]

### Resumen de Cierre y Verificación Oficial (RF15)
- **Fecha de Cierre:** 2026-11-01
- **Modelos y Métodos Operativos (`ventas/models.py`):**
  * `PuntoVenta.get_productos_disponibles()`: QuerySet dinámico gobernado por la base de datos real que combina productos asignados directamente (`puntos_venta`) y productos presentes en sus menús/cartas activas (`menus__activo=True`), filtrando estrictamente productos activos (`activo=True`) y aplicando `.distinct()`.
  * `Producto.esta_disponible_en(punto_venta)`: Validador de disponibilidad del producto para un local físico específico.
  * `Producto.to_mesero_dict()`: Serializador de producto hacia la interfaz táctil del Mesero, eliminando la lista hardcodeada y gobernando categorías, destinos operativos y precios en vivo desde la base de datos.
  * `Menu.productos_activos()` y `Menu.esta_vacio()`: Detección y gestión de cartas vacías o sin productos vigentes.
- **Servicios Centralizados y Lógica de Negocio (`ventas/utils.py`):**
  * `validar_disponibilidad_producto(producto, punto_venta)`: Servicio blindado de validación server-side que rechaza con `ValidationError`:
    - Productos inexistentes en el catálogo;
    - Productos desactivados (`activo=False`);
    - Productos no asignados ni en `puntos_venta` ni en cartas activas del local especificado (`RF15`).
- **Control de Terminales y Vistas (`ventas/views.py`):**
  * `crear_ticket` (POS Cajero): Validación estricta server-side en transacción atómica que rechaza con HTTP 400 cualquier intento de venta cruzada donde una terminal intente colar productos de otro local o productos deshabilitados. En modo GET, filtra el catálogo `productos_activos` mostrando únicamente la oferta oficial del local de la caja.
  * `mesero` (`enviar_comanda`): Validación server-side de disponibilidad en el punto de venta de la mesa seleccionada. Reemplazo del catálogo hardcodeado de 200 líneas por consulta en vivo a la BD mediante `local_actual.get_productos_disponibles()`. Soporte de mensajes de error limpios y controlados para meseros.
  * `poblar_safari`: Catálogo base de alimentos, bebidas y cafetería registrado en la BD con vinculación explícita a sus puntos de venta correspondientes (Restaurante Central, Cafetería La Selva, Kiosco Oasis).
- **Pruebas Automatizadas y Calidad:**
  * Tests específicos RF15 (`SafariRF15PosicionamientoProductosMenusTests`): 13/13 tests OK.
  * Suite completa del sistema: 185/185 tests pasados exitosamente en 340.5s (0 fallos, 0 errores, 100% verde).
  * System check `py manage.py check`: 0 incidencias.
  * Verificación manual de los 4 roles (Administrador, Cajero, Mesero, Cocinero): 100% verificado (`scratch/verificar_rf15.py`).

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

# RF16 — CONTROL DE TIEMPOS DE ATENCIÓN — [ESTADO: COMPLETADO Y CERRADO (197/197 OK)]

### Resumen de Cierre y Verificación Oficial (RF16)
- **Fecha de Cierre:** 2026-11-01
- **Modelos y Métodos Operativos (`ventas/models.py`):**
  * `Pedido.fecha_entregado`: Property getter y setter que recupera el timestamp inmutable de la primera entrega registrada (`self.entregas.order_by('id').first().fecha_hora_entrega`) o soporta override en memoria para simulación y pruebas.
  * `Pedido._calcular_delta_segundos(dt_fin, dt_inicio)`: Motor de cálculo temporal timezone-aware blindado contra desfases naive/aware y diferencias a través de medianoche.
  * `Pedido.get_tiempo_cola_minutos(en_curso=False)` y `get_tiempo_cola_segundos(en_curso=False)`: Tiempo transcurrido desde creación de la comanda hasta el inicio de su preparación en cocina/barra (`fecha_inicio_preparacion - creado_en`). Si `en_curso=True` y está pendiente, calcula tiempo transcurrido en vivo.
  * `Pedido.get_tiempo_preparacion_minutos(en_curso=False)` y `get_tiempo_preparacion_segundos(en_curso=False)`: Tiempo culinario transcurrido desde inicio de preparación hasta marcado como listo (`fecha_listo - fecha_inicio_preparacion`).
  * `Pedido.get_tiempo_despacho_minutos(en_curso=False)` y `get_tiempo_despacho_segundos(en_curso=False)`: Tiempo transcurrido desde que la comanda estuvo lista hasta su entrega física al comensal (`fecha_entregado - fecha_listo`).
  * `Pedido.get_tiempo_espera_total_minutos(en_curso=False)` y `get_tiempo_espera_total_segundos(en_curso=False)`: Tiempo global desde creación de la comanda hasta entrega comensal (`fecha_entregado - creado_en`). Implementa política estricta de *incompletos no inventados*: pedidos no entregados retornan `None` para no falsear auditorías, salvo que explícitamente se solicite cálculo en curso (`en_curso=True`).
  * `Pedido.validar_orden_temporal()`: Validador cronológico estricto que certifica la secuencia `creado_en <= fecha_inicio_preparacion <= fecha_listo <= fecha_entregado`, retornando `(es_valido, lista_inconsistencias)` y garantizando duraciones no negativas (`max(0.0, ...)`).
  * `Pedido.get_metricas_tiempos(en_curso=False)`: Diccionario consolidado de métricas, timestamps y validaciones para auditoría de servicio.
  * `Entrega.get_tiempo_desde_listo_minutos()` y `get_tiempo_desde_listo_segundos()`: Métodos auxiliares en modelo de auditoría de entrega.
- **Servicios Centralizados y Lógica de Negocio (`ventas/utils.py`):**
  * `formatear_fecha_hora_chile(dt)`: Formateador en zona horaria oficial de Chile (`America/Santiago`), robusto ante datetimes naive y aware.
  * `calcular_metricas_tiempos_pedido(pedido, en_curso=False)`: Servicio que enriquece las métricas temporales con strings chilenos formateados, metadata de venta, mesa y local.
  * `calcular_tiempos_promedio_local(punto_venta=None, fecha=None, pedidos_qs=None)`: Agregador de promedios de tiempos de atención (espera total, preparación cocina, tiempo en cola, despacho, mínimos y máximos) calculado exclusivamente a partir de órdenes efectivamente entregadas, evitando que pedidos pendientes, en preparación o cancelados distorsionen los tiempos de servicio.
- **Interfaces, Dashboards y Auditoría (`ventas/views.py` y templates):**
  * `administrador_historial`: Trazabilidad enriquecida en bitácora de entrega de pedidos, detallando minutos totales de atención y desglose de tiempo de preparación en cocina.
  * `administrador_local`: Inclusión en context de `promedios_tiempos` y despliegue en `administrador_local.html` de 4 tarjetas KPI con bordes temáticos (Espera Total Promedio, Prep. Cocina Promedio, Tiempo en Cola Promedio, Comandas Despachadas).
- **Pruebas Automatizadas y Calidad:**
  * Tests específicos RF16 (`SafariRF16ControlTiemposAtencionTests`): 12/12 tests OK.
  * Suite completa del sistema: 197/197 tests pasados exitosamente en 394.2s (0 fallos, 0 errores, 100% verde).
  * System check `py manage.py check`: 0 incidencias.
  * Verificación manual de los 4 roles (Administrador, Cajero, Mesero, Cocinero): 100% verificado (`scratch/verificar_rf16.py`).

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

# RF17 — GESTIÓN DE OCUPACIÓN DE MESAS — [ESTADO: COMPLETADO Y CERRADO (207/207 OK)]

### Resumen de Cierre y Verificación Oficial (RF17)
- **Fecha de Cierre:** 2026-11-01
- **Migración Aplicada:** `0020_mesa_fecha_ocupacion.py` agregando campo `fecha_ocupacion` a `Mesa`.
- **Modelos y Métodos Operativos (`ventas/models.py`):**
  * `Mesa.fecha_ocupacion`: Timestamp persistente de inicio de la ocupación actual de la mesa física.
  * `Mesa.get_venta_activa()`: Localiza la cuenta abierta en consumo vinculada a la mesa (`ventas.filter(estado='ABIERTA').first()`).
  * `Mesa.get_inicio_ocupacion()`: Prioriza `fecha_ocupacion` explícita o la infiere de `venta_activa.fecha_hora`, permitiendo reconstruir el 100% del estado tras reinicios o recargas.
  * `Mesa.esta_ocupada()` y `Mesa.esta_disponible()`: Verificadores exactos de disponibilidad operativa.
  * `Mesa.get_duracion_ocupacion_minutos(ahora=None)` y `get_duracion_ocupacion_segundos(ahora=None)`: Cálculo no negativo de duración en curso.
  * `Mesa.ocupar(timestamp=None, guardar=True)`: Marca la mesa como ocupada; blindado contra mesas `INACTIVA` y doble ocupación concurrente con `ValidationError`.
  * `Mesa.liberar(forzar=False, guardar=True)`: Blindaje estricto que rechaza la liberación si la mesa mantiene una cuenta abierta con consumos pendientes de cobro (`ValidationError`).
  * `Mesa.get_resumen_ocupacion()`: Diccionario estructurado con estado, timestamps, duración, venta activa y cantidad de rondas.
- **Servicios Centralizados y Lógica de Negocio (`ventas/utils.py`):**
  * `validar_ocupacion_mesa(mesa, permitir_si_misma_venta=None)`: Validador server-side de aptitud operativa ante mesas inactivas o doblemente ocupadas.
  * `liberar_mesa_operativa(mesa, usuario=None, forzar=False)`: Servicio atómico seguro con control de integridad de cuentas abiertas.
  * `calcular_metricas_ocupacion_local(punto_venta)`: Agregador de tasas de ocupación, mesas libres/ocupadas/inactivas y duración promedio por local.
- **Control de Terminales y Vistas (`ventas/views.py`):**
  * `mesero` (`liberar_mesa`): Invoca `liberar_mesa_operativa()`, impidiendo liberar mesas con cuentas abiertas en consumo.
  * `mesero` (`ocupar_mesa`): Ejecutado en transacción atómica con `select_for_update()`, bloqueando doble ocupación concurrente.
  * `mesero` (`cerrar_cuenta_mesa`): Libera la mesa y resetea `fecha_ocupacion` atómicamente al confirmarse el pago.
  * `mesero` (`reasignar_mesa`): Transfiere el timestamp original de ocupación a la mesa destino y libera la mesa origen.
  * `mesero` (`enviar_comanda`): Rechaza pedidos en mesas inactivas; al añadir rondas adicionales (Ronda 2, 3...) preserva intacto el timestamp de inicio ("nueva ronda no reinicia tiempo").
  * `cuentas_abiertas_json`: Incluye duración de ocupación calculada en vivo desde la base de datos.
- **Pruebas Automatizadas y Calidad:**
  * Tests específicos RF17 (`SafariRF17GestionOcupacionMesasTests`): 10/10 tests OK.
  * Suite completa del sistema: 207/207 tests pasados exitosamente en 409.8s (0 fallos, 0 errores, 100% verde).
  * System check `py manage.py check`: 0 incidencias.
  * Verificación manual de los 4 roles (Administrador, Cajero, Mesero, Cocinero): 100% verificado (`scratch/verificar_rf17.py`).

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

# RF18 — REPORTES Y ESTADÍSTICAS — [ESTADO: COMPLETADO Y CERRADO (220/220 OK)]

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

### Estado de Cierre de RF18 (01/11/2026)
- **Estado**: COMPLETADO Y CERRADO (100%).
- **Pruebas Automatizadas**: 13/13 pruebas unitarias e integración en `SafariRF18ReportesEstadisticasTests`. Suite completa: 220/220 tests en verde (388.5s).
- **Check Django**: `python manage.py check` con 0 errores y 0 advertencias.
- **Regresión 4 Roles**: Verificada al 100% en `scratch/verificar_rf18.py` (Administrador, Cajero, Mesero, Cocina) con control de acceso RBAC.
- **Erradicación de Mocks**: Purga total de variables y matrices simuladas ($49.5M, $23.8M, 84 fake tickets, `HISTORICO_15_MESES_DATOS`). Gráficos y tablas dinámicos gobernados exclusivamente por ORM real agrupado.
- **Motor Estadístico Centralizado**: Función `generar_reporte_estadistico_integral()` en `ventas/utils.py` soportando filtros dinámicos por rango de fechas (con sanitización contra rangos invertidos), Punto de Venta, usuario cajero y modalidad de atención.
- **Ranking Top 10**: Agregación por volumen y recaudación preservando productos históricos desactivados para auditoría contable.
- **Integración Operativa**: Métricas de tiempos culinarios (RF16) calculadas exclusivamente sobre órdenes válidas entregadas; métricas de ocupación y rotación de mesas (RF17) en vivo.
- **Exportación Oficial**: `obtener_datos_reporte()`, `generar_excel_ventas()` y `generar_word_ventas()` operando 100% sobre `Venta.objects.filter(estado='PAGADA')` sin fallbacks simulados.

---

# HISTÓRICO — ETAPA FINAL — AUDITORÍA INTEGRAL RF01–RF18 YA EJECUTADA

> Esta etapa fue ejecutada y culminó con la suite oficial de 220/220 pruebas aprobadas y el cierre al 100% de RF01–RF18.

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

> [!CAUTION]
> Este bloque se conserva exclusivamente como referencia histórica de diseño y robustez. Las instrucciones internas ya fueron ejecutadas o superadas y **NO son tareas vigentes**.

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

### HISTÓRICO — ORDEN DE EJECUCIÓN RF05–RF18 YA EJECUTADA / NO VIGENTE
Todo el contenido de esta subsección describe la secuencia usada durante el desarrollo y no constituye trabajo pendiente.

1. Se auditó la implementación exacta de RF05.
2. Se implementó y cerró RF05 con pruebas.
3. Se detuvo y devolvió `AI_CONTEXT.md` para revisión de ChatGPT/usuario.
4. Solo después se avanzó con RF07.
5. Se repitió el mismo ciclo para RF10, RF13/16, RF17 y RF18 hasta el cierre completo al 100% (220/220 pruebas).

La implementación siguió una secuencia incremental para detectar regresiones y mantener trazabilidad, completándose en su totalidad.

---
### HISTÓRICO — HITOS SEMANA 10 Y SEMANA 11 YA COMPLETADOS

#### Semana 10 — Clase 13/10/2026 — HISTÓRICO / COMPLETADO
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

Estado registrado en ese momento frente a Semana 10:
- Proyecto Django: YA EXISTE.
- Login real desde BD: YA EXISTE.
- Perfiles/roles actuales: ADMINISTRADOR, CAJERO, MESERO y COCINERO.
- Validaciones de credenciales, usuario inactivo y aislamiento de roles: YA EXISTEN.
- En ese momento faltaba dejar completamente demostrable y testeado el bloque de manejo de errores y robustez/vulnerabilidades (posteriormente completado al 100%).

#### HISTÓRICO — Orden técnica Semana 10 ya ejecutada
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

#### Semana 11 — Clase 20/10/2026 — HISTÓRICO / COMPLETADO
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

#### HISTÓRICO — Objetivos definidos antes de la clase del 20/10, ya ejecutados
1. **Gestión de Usuarios**
   - Se definió como objetivo consolidar el CRUD existente de trabajadores/usuarios como evidencia de Semana 11.
   - Se debía confirmar crear, listar/buscar, modificar, activar/desactivar y manejo de contraseña.
   - Se confirmaron validaciones y permisos de Administrador; posteriormente quedó completado.

2. **Gestión de Puntos de Venta**
   - Se definió como objetivo consolidar el CRUD existente como segunda evidencia real de Semana 11.
   - Se debía confirmar crear, modificar, activar/desactivar/eliminar protegido.
   - Se confirmó que un local con historial no pierde datos; posteriormente quedó completado.

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
### RECORDATORIO PARA FASE DOCUMENTAL / NO PRIORIDAD ACTUAL — ENTREGA 3
> [!IMPORTANT]
> **No modificar documentos Word antiguos.** Todo lo listado a continuación se aplicará directamente sobre el **NUEVO INFORME** de la Entrega 3 cuando el usuario indique su inicio:
>
> 1. **Sincronización del Modelo Lógico 1:1 con `models.py` (Rúbrica 2.1.4.8 - 10 Puntos):**
>    - En el nuevo informe, el diagrama relacional debe contener **todas las entidades vigentes reales** implementadas en Django y en el script físico DDL. **No asumir 19 entidades**: antes del informe se debe auditar `models.py` completo y contar el total actual:
>      - `auth_user`, `perfil_empleado` (con rol `COCINERO`), `alerta_traslado`.
>      - `punto_venta`, `jornada`, `caja`.
>      - `mesa`, `categoria`, `producto`, `precio_especial`, `menu`.
>      - `venta`, `detalle_venta`.
>      - `pedido`, `detalle_pedido`, `ticket`, `entrega`.
>      - `consumo_interno`, `detalle_consumo_interno`.
>    - Ejecutar `generar_word_modelo_datos.py` para compilar el diagrama en alta resolución 300 DPI (`diagrama_erd_parque_safari.png`) con enrutamiento ortogonal limpio (sin líneas que crucen cajas ni tapen texto).
>    - Reemplazar la imagen en el nuevo documento Word asegurando proporción panorámica (ancho ~6.4 in, alto ~4.05 in) para que no se deforme ni borre.
>    - En el script SQL físico dentro del informe, verificar que `chk_rol_valido` incluya `'COCINERO'`.
>    - Incluir el diccionario descriptivo de **todas las tablas vigentes reales** con sus PK, FK, tipos y restricciones.
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

### RECORDATORIO ACADÉMICO / NO PRIORIDAD ACTUAL — Calificación Oficial Informe 2: **78,70 / 100,00**
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

### 1. [2.1.4.9] Configuración del Motor de Base de Datos (PostgreSQL / MySQL) [PRIORIDAD INDICADA EN LA RETROALIMENTACIÓN ORIGINAL — NO PRIORIDAD ACTUAL]
- **Puntaje Obtenido:** 1.95 / 5.0 pts (En desarrollo)
- **Observación Docente:** *"settings.py mantiene la configuración predeterminada de SQLite y no presenta la conexión requerida a MySQL. El informe propone PostgreSQL, pero esta configuración tampoco se encuentra aplicada en el proyecto entregado."*
- **Nota del Usuario:** *"esto debemos ver urgente"*.
- **Acción sugerida/solicitada en la retroalimentación original para una futura fase documental:**
  - Configurar en `Venta_safari/settings.py` el soporte formal para PostgreSQL / MySQL mediante variables de entorno (`DATABASE_URL` o bloque `DATABASES` dinámico).
  - Incluir el adaptador correspondiente (`psycopg2-binary` para PostgreSQL y/o `mysqlclient`/`PyMySQL` para MySQL) en `requirements.txt`.
  - Proveer un fallback condicional inteligente a SQLite para desarrollo local sin servidor activo, pero asegurando que la configuración formal por defecto del proyecto apunte a PostgreSQL/MySQL tal como lo declara el informe y el modelo físico.
  - Asegurar coherencia entre el texto del informe (que menciona PostgreSQL en infraestructura y script DDL) y `settings.py`.

### 2. [2.1.3.5] Interfaz Específica para Cocina / Cocinero (KDS - Kitchen Display System) [PRIORIDAD INDICADA EN LA RETROALIMENTACIÓN ORIGINAL — NO PRIORIDAD ACTUAL]
- **Puntaje Obtenido:** 3.65 / 5.0 pts (Habilitado)
- **Observación Docente:** *"El prototipo presenta login, perfiles, navegación, ventas, caja, mesas, comandas, tickets, administración y reportes. Sin embargo, falta una interfaz específica para Cocina/Cocinero que permita visualizar pedidos pendientes, gestionar su preparación y comunicar al mesero cuáles están listos para ser servidos."*
- **Acción sugerida/solicitada en la retroalimentación original para una futura fase documental:**
  - Crear la vista y plantilla dedicada para Cocina (`/cocina/` / `cocina.html` / KDS):
    - Visualización en tarjetas táctiles (tipo Kanban) de pedidos entrantes clasificados por destino (`COCINA` vs `BARRA`).
    - Flujo de estados interactivo: `PENDIENTE` -> `EN PREPARACIÓN` -> `LISTO PARA ENTREGA`.
    - Botón de acción para el cocinero (*"Comenzar Preparación"*, *"Marcar Plato Listo"*).
    - Notificación visual/comunicación al módulo de Mesero para alertar que los platos de la mesa están listos para ser retirados y servidos.
  - Agregar nuevo rol o perfil específico de Cocinero / Jefe de Cocina si aplica, o permitir acceso operativo de cocina.

### 3. [2.1.5.12] Coherencia en "Cero Credenciales en Código" (SECRET_KEY en settings.py) [PRIORIDAD INDICADA EN LA RETROALIMENTACIÓN ORIGINAL — NO PRIORIDAD ACTUAL]
- **Puntaje Obtenido:** 7.3 / 10.0 pts (Habilitado)
- **Observación Docente:** *"Los estándares están ampliamente desarrollados; sin embargo, el informe establece explícitamente una política de 'Cero Credenciales en Código' que prohíbe mantener SECRET_KEY directamente en los archivos, mientras que settings.py mantiene esta clave escrita en el código. Debe existir coherencia entre los estándares definidos y su aplicación."*
- **Nota del Usuario:** *"debemos ajuntar"*.
- **Acción sugerida/solicitada en la retroalimentación original para una futura fase documental:**
  - Extraer `SECRET_KEY` de `Venta_safari/settings.py` utilizando `os.environ.get('SECRET_KEY')` o biblioteca de variables de entorno (`python-dotenv` / `decouple`).
  - Crear archivo `.env.example` en la raíz del repositorio con variables de muestra.
  - Verificar que el archivo `.env` real esté explícitamente protegido y excluido en `.gitignore`.
  - Asegurar coherencia absoluta entre las políticas redactadas en el informe y los archivos del repositorio.

### 4. [2.1.6.13] Documentación y Ejecución de Pruebas de Rendimiento (Performance Testing) [PRIORIDAD INDICADA EN LA RETROALIMENTACIÓN ORIGINAL — NO PRIORIDAD ACTUAL]
- **Puntaje Obtenido:** 7.3 / 10.0 pts (Habilitado)
- **Observación Docente:** *"Se presentan y ejecutan pruebas unitarias y de integración, pero falta desarrollar y documentar con la misma claridad un conjunto específico de pruebas de rendimiento."*
- **Nota del Usuario:** *"debemos aclarar mas esto"*.
- **Acción sugerida/solicitada en la retroalimentación original para una futura fase documental:**
  - Desarrollar, ejecutar y documentar formalmente pruebas de rendimiento (*Performance / Load Testing*):
    - Medición de latencia y tiempos de respuesta (ms) en endpoints críticos: Login, creación de comanda en mesero, despacho de tickets, consulta de dashboard con 15 meses de transacciones.
    - Simulación de carga concurrente (ej. 20, 50, 100 usuarios simultáneos en hora pico de Parque Safari) utilizando herramientas como Locust, k6, Apache Benchmark (`ab`) o script automatizado de benchmarking en Python.
    - Incluir en el informe una sección y tabla formal de resultados de rendimiento: tiempo de respuesta promedio, percentil 95, rendimiento de peticiones por segundo (RPS), consumo de CPU y memoria RAM.

### 5. [2.1.4.8] Sincronización Completa entre Modelo Lógico (Draw.io) y Físico (models.py) [PRIORIDAD INDICADA EN LA RETROALIMENTACIÓN ORIGINAL — NO PRIORIDAD ACTUAL]
- **Puntaje Obtenido:** 7.3 / 10.0 pts (Habilitado)
- **Observación Docente:** *"El modelo presenta correctamente entidades, claves y relaciones; sin embargo, el modelo lógico no representa completamente todas las entidades y relaciones que posteriormente aparecen implementadas en models.py y en el modelo físico."*
- **Acción sugerida/solicitada en la retroalimentación original para una futura fase documental:**
  - Actualizar el diagrama relacional en Draw.io para que represente el 100% de las tablas declaradas en el script SQL y en `ventas/models.py`.
  - Entidades a sincronizar e incorporar en el diagrama de Draw.io:
    - `AlertaTraslado` (relacionada con `auth_user` y `punto_venta` origen/destino).
    - `PrecioEspecial` (relacionada con `producto`).
    - `Menu` y tabla intermedia `MenuProductos` / `ProductoPuntosVenta`.
    - `Entrega` (relacionada con `pedido`, `ticket` y `auth_user`).
    - `ConsumoInterno` y `DetalleConsumoInterno` (relacionada con `auth_user`, `punto_venta` y `producto`).
  - Reemplazar la imagen en el informe garantizando que modelo lógico, modelo físico y `models.py` sean un reflejo espejo 1:1.

### 6. [2.1.1.2] Enlace al Proyecto de Azure DevOps en el Informe [PRIORIDAD INDICADA EN LA RETROALIMENTACIÓN ORIGINAL — NO PRIORIDAD ACTUAL]
- **Puntaje Obtenido:** 1.95 / 5.0 pts (En desarrollo)
- **Observación Docente:** *"En el informe NO se evidencia el enlace para acceder y lograr revisar el proyecto en Azure DevOps."*
- **Nota del Usuario:** *"este fue mi error asi que recordatorio"*.
- **Acción sugerida/solicitada en la retroalimentación original para una futura fase documental:**
  - Agregar de forma visible y destacada en el informe (en la portada, en la introducción y en la sección 2.2 de Azure DevOps) el enlace directo hipervinculado a la organización y proyecto de Azure DevOps:
    `https://dev.azure.com/[organizacion]/[proyecto]`
  - Verificar que el enlace posea permisos públicos o que el usuario docente (`Miguel Angel López Jerez`) tenga concedidos los permisos de lectura (*Stakeholder* / *Basic*).

### 7. [2.1.2.3] Redacción Estrictamente Impersonal en Paradigma 4+1 [PRIORIDAD INDICADA EN LA RETROALIMENTACIÓN ORIGINAL — NO PRIORIDAD ACTUAL]
- **Puntaje Obtenido:** 3.65 / 5.0 pts (Habilitado)
- **Observación Docente:** *"Las cinco vistas están desarrolladas; sin embargo, se utilizan expresiones en primera persona como 'nos permite' y 'nos permitirán'. La redacción del informe debe mantenerse de manera impersonal."*
- **Acción sugerida/solicitada en la retroalimentación original para una futura fase documental:**
  - Realizar un barrido ortotipográfico y estilístico completo en el informe, erradicando toda conjugación en primera persona ("nos permite", "hicimos", "definimos", "nuestro sistema").
  - Sustituir por redacción técnica impersonal y pasiva refleja: *"el modelo permite"*, *"la arquitectura posibilita"*, *"se define"*, *"se implementó"*, *"el sistema desarrollado"*.

### 8. [2.1.3.7] Plantilla Oficial de Retroalimentación de Pares [PRIORIDAD INDICADA EN LA RETROALIMENTACIÓN ORIGINAL — NO PRIORIDAD ACTUAL]
- **Puntaje Obtenido:** 1.95 / 5.0 pts (En desarrollo)
- **Observación Docente:** *"El formato con los comentarios de las revisiones a modo de retroalimentación por parte de otros equipos, NO es la facilitada por el docente."*
- **Nota del Usuario:** *"esto debo charlar con el docente porque si le abjunte en un archvio aparte"*.
- **Acción sugerida/solicitada en la retroalimentación original para una futura fase documental:**
  - Aclarar con el docente la entrega previa del archivo adjunto.
  - Transcribir e insertar la información directamente dentro de la plantilla oficial de la Semana 7 facilitada por el profesor, incorporándola de manera visible en el cuerpo principal del informe.

### 9. [2.1.6.15] Registro y Presentación Continua de Avances en Clases [PRIORIDAD INDICADA EN LA RETROALIMENTACIÓN ORIGINAL — NO PRIORIDAD ACTUAL]
- **Puntaje Obtenido:** 3.65 / 5.0 pts (Habilitado)
- **Observación Docente:** *"Existen semanas de clases donde no se presentan los avances requeridos por el docente."*
- **Acción sugerida/solicitada en la retroalimentación original para una futura fase documental:**
  - Mantener al día la bitácora semanal y presentar puntualmente los avances en cada sesión de clase presencial según el calendario del curso.

---

## 3. estado actual
- RF01–RF18: **COMPLETADOS AL 100%**.
- suite vigente: **220/220 pruebas aprobadas**.
- `python manage.py check`: **0 incidencias**.
- migraciones `ventas`: **20 aplicadas**.
- motor activo: **SQLite**.
- modelos/tablas vigentes en `ventas`: **25**.
- roles operativos: ADMINISTRADOR, CAJERO, MESERO y COCINERO.
- mocks en flujos evaluables: **0%**.
- repositorio:
  - `.env` protegido y no rastreado;
  - `db.sqlite3` fuera del índice Git y conservado localmente.
- rendimiento de regresión vigente:
  - 20 usuarios concurrentes;
  - 100 peticiones;
  - 100% éxito;
  - 166.59 RPS;
  - 70.84 ms promedio;
  - P95 524.29 ms.
- siguiente fase: **Preparación para revisión y retroalimentación. Desarrollo funcional detenido. Fase documental pendiente de autorización expresa del usuario.**
- los bloques con conteos anteriores o tareas antiguas son históricos y no representan órdenes vigentes.
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
  - motivo por el que es relevante: Suite oficial de 220 pruebas automatizadas que cubre RF01–RF18, seguridad, permisos, concurrencia, persistencia, tickets, impresión, consumo interno, tiempos, ocupación, reportes y regresión.
- archivo: models.py
  - ruta: c:/Users/pc/Desktop/safari Pilar/ventas/models.py
  - función: Modelo de dominio y persistencia del sistema
  - motivo por el que es relevante: Contiene las 25 entidades vigentes, relaciones, restricciones, estados operativos, trazabilidad y reglas de integridad de RF01–RF18.
- archivo: utils.py
  - ruta: c:/Users/pc/Desktop/safari Pilar/ventas/utils.py
  - función: Servicios de negocio centralizados
  - motivo por el que es relevante: Centraliza validaciones, precios especiales, tickets, impresión, consumos internos, entregas, tiempos, ocupación y reportes reales.
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

## CHECKLIST FINAL PRE-REVISIÓN

- [x] **Estado RF01–RF18**: 100% implementados, testeados y cerrados conforme al alcance oficial.
- [x] **Suite de Pruebas**: 220 de 220 pruebas automatizadas en verde (0 fallos, 0 errores en 388.5s).
- [x] **Chequeo de Sistema**: `python manage.py check` con 0 incidencias (código limpio).
- [x] **Migraciones**: 20 migraciones de la app `ventas` aplicadas al 100% en base de datos.
- [x] **Motor de Base de Datos**: SQLite activo y operativo para desarrollo local; `.env` listo para PostgreSQL si se requiere en despliegue.
- [x] **4 Roles Operativos**: Verificados en HTTP 200 y protegidos con RBAC (`ADMINISTRADOR`, `CAJERO`, `MESERO`, `COCINA`).
- [x] **Modelos / Tablas**: 25 modelos auditados y mapeados 1:1 con PK, FKs y restricciones de integridad.
- [x] **Seguridad**: Contraseñas con hashing PBKDF2/SHA-256, cero texto plano, cambio forzoso de clave en primer login, `.env` protegido por `.gitignore`.
- [x] **Higiene de Repositorio**: `db.sqlite3` fuera del índice de Git (untracked) y preservado localmente; cero credenciales o secretos rastreados.
- [x] **Mocks**: 0% datos simulados en flujos evaluables; KPIs, reportes y gráficos operan exclusivamente sobre ORM real.
- [x] **Rendimiento**: Benchmark reproducible de 20 usuarios concurrentes validado empíricamente (166.59 RPS, 70.84 ms prom, 100% éxito).
- [x] **Pendientes Críticos**: Ningún bloqueante funcional. Los recordatorios de evaluación e informe quedan conservados para la fase documental posterior del usuario.
- [x] No existe ninguna orden activa anterior.
- [x] Todo contenido imperativo histórico está contextualizado como pasado/no vigente.
- [x] Recordatorios académicos preservados sin prioridad operativa actual.
- [x] STOP DESARROLLO TOTAL.

---

## 6. errores actuales y observaciones pendientes
- **Bloqueantes funcionales actuales: ninguno conocido.**
- **Pendientes técnicos para revisión: ninguno crítico.**
- SQLite continúa como entorno activo de desarrollo.
- PostgreSQL/MySQL se conserva únicamente como recordatorio académico futuro.
- fase documental pendiente de autorización expresa del usuario.
- módulos huéspedes/cabañas/desayuno/ofertas permanecen congelados y fuera del núcleo evaluable.
- cualquier problema nuevo debe registrarse únicamente si es reproducible, indicando archivo, función/línea, pasos, severidad y solución.
## 7. dudas para ChatGPT
- no hay dudas funcionales activas.
- la prioridad definida por el usuario es dejar el proyecto en su mejor estado posible para revisión y retroalimentación.
- recordatorios académicos/evaluación se mantienen, pero serán tratados posteriormente por el usuario.
## 8. respuesta de ChatGPT
- No existe ninguna orden de desarrollo vigente.
- Proyecto congelado para revisión y retroalimentación.
- STOP DESARROLLO TOTAL hasta nueva instrucción expresa del usuario.
## 9. HISTÓRICO — Auditoría de Convergencia y Mapa de Convergencia 06-Oct

> [!NOTE]
> **HISTÓRICO — estado al 06/10/2026** (Conservado para trazabilidad académica; no representa el estado vigente actual de 220/220 tests ni los 18 RF cerrados).

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

### H. MAPA DE CONVERGENCIA 06-OCT [HISTÓRICO — NO VIGENTE]

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

2. HISTÓRICO — IMPLEMENTADO PERO REQUERÍA CORRECCIÓN AL 06-OCT; RESUELTO POSTERIORMENTE
----------------------------------------------------------------------------------------
- 'administrador_local': Lee ventas reales de BD, pero en get_locales_data() aún concatena tickets mock
  demo para los locales 1, 2 y 3.
- Extracción de notas en monitor de Administrador: En get_locales_data(), los tickets reales aún no extraen
  el texto de DetallePedido.observaciones hacia el array JSON de visualización.
- Terminal de Mesero: Permite cambiar de local mediante '?local_id=' en la URL en vez de aislar
  estrictamente al mesero a su 'perfil.punto_venta_actual'.

3. HISTÓRICO — MOCK / HARDCODEADO AL 06-OCT; RESUELTO POSTERIORMENTE
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

5. HISTÓRICO — RIESGOS DE INTEGRIDAD IDENTIFICADOS AL 06-OCT
----------------------------------------------------------------------------------------
- Asimetría transaccional: Mesero impacta tablas reales de SQLite mientras Cajero impacta 'localStorage'.
- Precios y totales confiados al cliente: En 'enviar_comanda', el precio se toma del JSON del cliente sin
  revalidar contra el precio oficial en tabla Producto de SQLite (requiere RF05).
- Despacho entre locales: Un mesero podría emitir comandas en mesas de otro punto de venta vía URL.

6. HISTÓRICO — RIESGOS DE SEGURIDAD / REPOSITORIO IDENTIFICADOS AL 06-OCT
----------------------------------------------------------------------------------------
- 'db.sqlite3' versionado en Git: Riesgo de sobreescritura de datos locales entre clones.
- 'SECRET_KEY' fija y 'DEBUG = True' en 'settings.py': Requiere migrar a variables de entorno para producción.

7. HISTÓRICO — PRUEBAS QUE FALTABAN AL 06-OCT; CUBIERTAS POSTERIORMENTE
----------------------------------------------------------------------------------------
- Prueba automatizada de notas libres: Verificar que 'DetallePedido.observaciones' almacene la nota enviada.
- Prueba de validación de precios del servidor en comanda de mesero.
- Pruebas automatizadas para la persistencia real del Cajero (cuando se migre de localStorage a SQLite).
- Prueba de restricción de mesero a su local asignado.

9. HISTÓRICO — REGLA FUNCIONAL QUE ESTABA PENDIENTE AL 06-OCT; RESUELTA
----------------------------------------------------------------------------------------
- Una mesa puede realizar múltiples rondas de pedidos dentro de una misma atención.
- La primera comanda no cierra la Venta.
- Las rondas siguientes deben reutilizar la misma Venta abierta de la Mesa.
- Cada ronda genera únicamente sus nuevos DetallePedido/Tickets.
- La cuenta final acumula todas las rondas.
- La Mesa se libera solo al cerrar/pagar la cuenta.
- Debe impedirse más de una Venta abierta simultánea para la misma Mesa.

8. HISTÓRICO — SIGUIENTE PASO RECOMENDADO AL 06-OCT; YA EJECUTADO
----------------------------------------------------------------------------------------
1. Sincronizar lectura de 'DetallePedido.observaciones' en 'get_locales_data()' para reflejar las notas
   en el modal de detalle del Administrador.
2. Unificar persistencia del Cajero a SQLite reutilizando la lógica atómica de Mesero (eliminando localStorage).
3. Avanzar formalmente a RF05: Catálogo Centralizado de Productos y Menús en SQLite.
========================================================================================
```

## 10. siguiente tarea
- Siguiente tarea de desarrollo: NINGUNA.
- Esperar revisión/retroalimentación o nueva instrucción expresa del usuario.
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
1. RF01–RF18 permanecen cerrados salvo regresión reproducible.
2. RF19–RF24 permanecen totalmente excluidos.
3. No agregar nuevas funcionalidades antes de revisión.
4. Suite vigente: 220/220; conteos menores son históricos.
5. Prioridad vigente: revisión y retroalimentación.
6. Huéspedes/cabañas/desayuno/ofertas permanecen congelados y fuera del núcleo evaluable.
7. No modificar Word, Draw.io ni informe oficial sin autorización expresa del usuario.
8. Recordatorios académicos/evaluación se conservan como referencia futura, pero no gobiernan el trabajo actual.
9. SQLite es el motor activo de desarrollo; no declarar PostgreSQL/MySQL como activo sin evidencia real.
10. `.env` debe permanecer protegido y fuera de Git; `db.sqlite3` no debe volver a versionarse.
11. Leer `AI_CONTEXT.md` antes de cambios importantes y actualizarlo solo después de cambios relevantes.
12. No inventar información, resultados, métricas, pruebas, rutas ni requisitos.
13. Registrar errores exactos y soluciones aplicadas.
14. No reactivar planes históricos ni órdenes antiguas.
15. Tras la limpieza pre-revisión: **STOP DESARROLLO** hasta nueva instrucción.
## 13. protocolo de trabajo ChatGPT ↔ Antigravity
- objetivo: Usar este archivo como canal único de contexto y coordinación técnica para el desarrollo del Proyecto Integrado.
- rol de ChatGPT: Revisar el estado informado en este archivo, contrastarlo con los requerimientos vigentes del Proyecto Integrado y proponer la siguiente orden técnica.
- rol de Antigravity: Ejecutar en el proyecto local las órdenes técnicas registradas en este archivo y luego actualizar el estado, cambios, errores y dudas.
