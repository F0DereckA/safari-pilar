"""
Punto de entrada oficial de la suite de pruebas de Venta Safari.

La suite monolítica heredada fue refactorizada modularmente en `ventas/test_suites/`
utilizando fixtures compartidos en `setUpTestData`, pruebas parametrizadas con `subTest()`,
hasher rápido exclusivo para entorno de tests (`FastTestPBKDF2PasswordHasher`),
y matriz de Contraste Positivo vs Negativo (`ContrasteAssertMixin`).

Los módulos internos de `ventas/test_suites/` no usan el prefijo `test_` para evitar
doble descubrimiento al ejecutar `py manage.py test ventas`.
"""

from ventas.test_suites.arquitectura_ui import (  # noqa: F401
    ArquitecturaEstaticosSimpleTests,
    ArquitecturaRenderCspYContrastTests,
)
from ventas.test_suites.autenticacion_seguridad_arco import (  # noqa: F401
    AutenticacionAccesoYSeguridadTests,
    PrivacidadConsentimientoYArcoTests,
)
from ventas.test_suites.catalogo_precios_promos_consumos import (  # noqa: F401
    CatalogoPosicionamientoYPromocionesTests,
    PreciosEspecialesConveniosPropinasYConsumosTests,
)
from ventas.test_suites.kds_impresion_reportes import (  # noqa: F401
    KdsCocinaBarraYComentariosTests,
    ReportesEstadisticasYGestionAdminTests,
    TicketsImpresionYTiemposAtencionTests,
)
from ventas.test_suites.pos_caja_mesas import (  # noqa: F401
    LocalesMesasReasignacionYOcupacionTests,
    OperacionJornadaCajaYAnulacionesTests,
)

__all__ = [
    'ArquitecturaEstaticosSimpleTests',
    'ArquitecturaRenderCspYContrastTests',
    'AutenticacionAccesoYSeguridadTests',
    'PrivacidadConsentimientoYArcoTests',
    'OperacionJornadaCajaYAnulacionesTests',
    'LocalesMesasReasignacionYOcupacionTests',
    'CatalogoPosicionamientoYPromocionesTests',
    'PreciosEspecialesConveniosPropinasYConsumosTests',
    'KdsCocinaBarraYComentariosTests',
    'TicketsImpresionYTiemposAtencionTests',
    'ReportesEstadisticasYGestionAdminTests',
]
