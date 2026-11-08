# Regla de Workspace: Orden Modular por Zonas (Venta Safari)

1. **Separación estricta de estáticos (`static/`):**
   - CSS exclusivamente en `static/css/<zona>/`.
   - JavaScript exclusivamente en `static/js/<zona>/`.
   - Imágenes exclusivamente en `static/img/<zona>/`.
   - Zonas oficiales: `global`, `acceso`, `administrador`, `cajero`, `mesero`, `kds`, `impresion`, `errores/400` y `errores/500`.
   - Prohibido escribir bloques `<style>` o `<script>` ejecutables dentro de plantillas `.html` (solo se permiten bloques declarativos `<script type="application/json">` para datos del servidor).

2. **Separación estricta de plantillas HTML:**
   - Plantillas de aplicación en `ventas/templates/ventas/<zona>/` (`acceso`, `administrador`, `cajero`, `mesero`, `kds`, `impresion`).
   - Plantillas de error HTTP en `templates/errores/400/` y `templates/errores/500/`.
   - Prohibido dejar plantillas `.html` sueltas fuera de su subcarpeta de zona.

3. **Higiene de la raíz del repositorio:**
   - No crear archivos temporales, imágenes, páginas HTML ni documentos Word/Excel en la raíz del proyecto.
   - Scripts auxiliares permanentes van en `scripts/`; entregables secundarios archivados van en `cosas para entregas futuras/`.

4. **Validación continua:**
   - Todo cambio debe mantener `py manage.py check` en 0 errores y el 100% de `py manage.py test ventas` aprobado.
