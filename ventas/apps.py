from django.apps import AppConfig
from django.db.backends.signals import connection_created


def activar_sqlite_wal(sender, connection, **kwargs):
    """Activa modo WAL (Write-Ahead Logging) y timeout ampliado para SQLite (Alta Concurrencia)"""
    if connection.vendor == 'sqlite':
        try:
            cursor = connection.cursor()
            cursor.execute('PRAGMA journal_mode = WAL;')
            cursor.execute('PRAGMA synchronous = NORMAL;')
            cursor.execute('PRAGMA busy_timeout = 20000;')
        except Exception:
            pass


class VentasConfig(AppConfig):
    name = 'ventas'

    def ready(self):
        connection_created.connect(activar_sqlite_wal)
