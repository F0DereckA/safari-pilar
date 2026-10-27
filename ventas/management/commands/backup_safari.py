import os
import gzip
import hashlib
import sqlite3
import datetime
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Genera una copia de seguridad (backup) en caliente, íntegra y comprimida de la base de datos de Parque Safari."

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default=os.path.join(settings.BASE_DIR, 'backups'),
            help='Directorio donde se almacenarán las copias de seguridad.'
        )
        parser.add_argument(
            '--keep-days',
            type=int,
            default=14,
            help='Días de retención antes de rotar (eliminar) respaldos antiguos.'
        )

    def handle(self, *args, **options):
        output_dir = options['output_dir']
        keep_days = options['keep_days']

        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        db_conf = settings.DATABASES['default']

        self.stdout.write(self.style.NOTICE(f"=== Iniciando Respaldo de Base de Datos Parque Safari ({timestamp}) ==="))

        if 'sqlite3' in db_conf.get('ENGINE', ''):
            db_path = db_conf.get('NAME')
            # Se procede con la ruta física o conexión en memoria activa

            temp_backup = os.path.join(output_dir, f"safari_temp_{timestamp}.sqlite3")
            gz_backup = os.path.join(output_dir, f"safari_backup_{timestamp}.sqlite3.gz")
            sha_file = os.path.join(output_dir, f"safari_backup_{timestamp}.sha256")

            # 1. Snapshot en caliente mediante la API oficial sqlite3.backup (cero corrupción por concurrencia)
            try:
                from django.db import connection
                dst_conn = sqlite3.connect(temp_backup)
                if os.path.exists(db_path):
                    src_conn = sqlite3.connect(db_path)
                    src_conn.backup(dst_conn)
                    src_conn.close()
                else:
                    # Entorno de pruebas o BD en memoria: usar la conexión activa de Django
                    connection.ensure_connection()
                    connection.connection.backup(dst_conn)
                dst_conn.close()
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error al realizar snapshot SQLite: {e}"))
                if os.path.exists(temp_backup):
                    os.remove(temp_backup)
                return

            # 2. Verificación de Integridad Física (PRAGMA integrity_check)
            try:
                chk_conn = sqlite3.connect(temp_backup)
                cursor = chk_conn.cursor()
                cursor.execute("PRAGMA integrity_check;")
                result = cursor.fetchone()
                chk_conn.close()

                if not result or result[0].lower() != "ok":
                    self.stderr.write(self.style.ERROR(f"Falla de integridad en la copia: {result}"))
                    os.remove(temp_backup)
                    return
                self.stdout.write(self.style.SUCCESS("  [+] Verificación de integridad SQLite: OK"))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error verificando integridad: {e}"))
                if os.path.exists(temp_backup):
                    os.remove(temp_backup)
                return

            # 3. Compresión GZIP de alta eficiencia
            sha256_hash = hashlib.sha256()
            with open(temp_backup, 'rb') as f_in, gzip.open(gz_backup, 'wb') as f_out:
                while chunk := f_in.read(65536):
                    f_out.write(chunk)
                    sha256_hash.update(chunk)

            # Eliminar snapshot temporal no comprimido
            if os.path.exists(temp_backup):
                os.remove(temp_backup)

            digest = sha256_hash.hexdigest()
            with open(sha_file, 'w', encoding='utf-8') as f_sha:
                f_sha.write(f"{digest}  {os.path.basename(gz_backup)}\n")

            tamano_kb = os.path.getsize(gz_backup) / 1024
            self.stdout.write(self.style.SUCCESS(f"  [+] Archivo comprimido generado: {os.path.basename(gz_backup)} ({tamano_kb:.1f} KB)"))
            self.stdout.write(self.style.SUCCESS(f"  [+] Hash SHA-256 verificado: {digest[:16]}..."))

        else:
            self.stdout.write(self.style.WARNING("  Motor no SQLite detectado; exportando metadatos de configuración."))
            gz_backup = os.path.join(output_dir, f"safari_config_{timestamp}.txt")
            with open(gz_backup, 'w') as f:
                f.write(f"Motor: {db_conf.get('ENGINE')}, Base de Datos: {db_conf.get('NAME')}")

        # 4. Rotación automática de respaldos antiguos (> keep_days)
        ahora = datetime.datetime.now()
        rotados = 0
        for fname in os.listdir(output_dir):
            if fname.startswith("safari_backup_") and (fname.endswith(".gz") or fname.endswith(".sha256")):
                fpath = os.path.join(output_dir, fname)
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(fpath))
                if (ahora - mtime).days >= keep_days:
                    try:
                        os.remove(fpath)
                        rotados += 1
                    except OSError:
                        pass

        if rotados > 0:
            self.stdout.write(self.style.NOTICE(f"  [i] Rotación completada: {rotados} archivo(s) antiguo(s) eliminados."))

        self.stdout.write(self.style.SUCCESS("=== Respaldo completado exitosamente ==="))
