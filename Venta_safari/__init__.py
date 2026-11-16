"""Inicialización del paquete núcleo Venta_safari (compatibilidad MySQL vía PyMySQL)."""

try:
    import MySQLdb  # noqa: F401
except ImportError:
    try:
        import pymysql

        # Compatibilidad con versiones de PyMySQL anteriores que reportan 1.4.6 ante Django 5/6
        if getattr(pymysql, "version_info", (0,)) < (2, 2, 1):
            pymysql.version_info = (2, 2, 1, "final", 0)
            pymysql.__version__ = "2.2.1"
        pymysql.install_as_MySQLdb()
    except ImportError:
        pass
