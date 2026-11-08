# Reglas Obligatorias de Orden y Arquitectura Modular — Venta Safari

Estas instrucciones son **obligatorias y permanentes** para todas las futuras interacciones sobre este proyecto. Ningún cambio debe romper este orden estructural.

## 1. Mapa Oficial de Carpetas del Proyecto

- `Venta_safari/`: Configuración núcleo de Django (`settings.py`, `urls.py`, `wsgi.py`, `asgi.py`).
- `ventas/`: Lógica backend de la aplicación (`models.py`, `views.py`, `urls.py`, `utils.py`, `middleware.py`, `validators.py`, `exportador_reportes.py`, `tests.py`, `migrations/`, `management/commands/`, `templatetags/`).
- `ventas/templates/ventas/<zona>/`: Plantillas HTML operativas clasificadas **estrictamente por zona** (prohibido dejar `.html` sueltos en la raíz de `ventas/templates/ventas/`):
  - `acceso/`: Login, cambio de clave expirada y acceso QR (`index.html`, `cambiar_clave_expirada.html`, `qr_acceso.html`).
  - `administrador/`: Panel general y submódulos administrativos (`administrador*.html`).
  - `cajero/`: Monitor de caja y punto de venta POS (`vendedor.html`, `vendedor_crear_ticket.html`).
  - `mesero/`: Mapa de mesas y comandas de salón (`mesero.html`).
  - `kds/`: Pantallas táctiles de producción (`cocina.html`, `barra.html`).
  - `impresion/`: Tickets térmicos digitales y reportes imprimibles (`ticket_impresion_digital.html`, `reporte_ventas_impresion.html`).
- `templates/errores/<familia>/`: Plantillas corporativas de errores HTTP divididas por código (prohibido dejar `.html` sueltos en `templates/`):
  - `400/`: `400.html`, `401.html`, `403.html`, `404.html`.
  - `500/`: `500.html`, `502.html`, `503.html`, `504.html`.
- `static/`: Todos los recursos estáticos separados por tipo (`css/`, `js/`, `img/`) y subdivididos simétricamente en las mismas zonas:
  - `static/css/<zona>/` (`global`, `acceso`, `administrador`, `cajero`, `mesero`, `kds`, `impresion`, `errores/400`, `errores/500`).
  - `static/js/<zona>/` (`global`, `acceso`, `administrador`, `cajero`, `mesero`, `kds`, `impresion`, `errores/400`, `errores/500`).
  - `static/img/<zona>/` (`global`, `acceso`, `administrador`, `cajero`, `mesero`, `kds`, `impresion`, `errores/400`, `errores/500`).
- `scripts/`: Scripts auxiliares de diagnóstico o verificación reproducible (ej. `scripts/verificar_rf18.py`).
- `backups/`: Respaldos comprimidos de base de datos generados por `backup_safari` (excluido de Git).
- `cosas para entregas futuras/`: Archivo separado para documentos Word/Excel o entregables fuera del núcleo activo (excluido de Git).

## 2. Reglas Estrictas para Nuevos Archivos y Modificaciones

1. **Cero CSS o JS incrustado en HTML:**
   - Está **prohibido** agregar bloques `<style>...</style>` o bloques `<script>...</script>` ejecutables dentro de archivos `.html`.
   - Todo estilo nuevo debe ubicarse en `static/css/<zona>/<modulo>.css` y enlazarse con `{% static %}`.
   - Toda lógica JavaScript nueva debe ubicarse en `static/js/<zona>/<modulo>.js` y enlazarse con `{% static %}`. Para pasar datos desde Django a JS, usar únicamente bloques declarativos `<script id="..." type="application/json">` o atributos `data-*`.
   - Toda imagen nueva debe guardarse en `static/img/<zona>/` y referenciarse con `{% static %}`.
2. **Raíz del proyecto limpia:**
   - Está **prohibido** crear archivos sueltos en la raíz del proyecto (ni `.html`, ni `.docx`, ni `.xlsx`, ni `.png`, ni scripts temporales).
   - Scripts de prueba puntuales van en el directorio de artefactos del agente o en `scripts/` si son permanentes. Documentos no esenciales van en `cosas para entregas futuras/`.
3. **Seguridad de contraseñas y datos sensibles:**
   - Cumplir sin excepción el hashing obligatorio de contraseñas y ocultamiento visual (`type="password"`), sin almacenar, comparar ni mostrar claves en texto plano en código, plantillas ni respuestas.
   - Nunca versionar `.env` ni `db.sqlite3`.
4. **Verificación obligatoria antes de finalizar cualquier tarea:**
   - Ejecutar `py manage.py check` (0 incidencias) y `py manage.py test ventas` (100% de la suite aprobada, incluyendo la prueba automática `test_migracion_estaticos_css_js_img_por_zonas`).
