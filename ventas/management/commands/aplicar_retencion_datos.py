from django.core.management.base import BaseCommand
from ventas.models import purgar_datos_por_retencion


class Command(BaseCommand):
    help = "Aplica las políticas definidas de retención y anonimización de datos personales (Venta Safari)."

    def add_arguments(self, parser):
        parser.add_argument('--dias-consentimiento', type=int, default=365, help='Días de retención de registros de consentimiento (por defecto 365).')
        parser.add_argument('--dias-inactivos', type=int, default=180, help='Días tras desactivación para anonimización automática (por defecto 180).')

    def handle(self, *args, **options):
        resultado = purgar_datos_por_retencion(
            dias_consentimiento=options['dias_consentimiento'],
            dias_inactivos=options['dias_inactivos'],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Retención aplicada: {resultado['cookies_anonimas_purgadas']} cookies anónimas purgadas, "
                f"{resultado['hashes_ip_purgados']} huellas IP/UA depuradas (>30d), "
                f"{resultado['consentimientos_expirados_purgados']} consentimientos expirados eliminados, "
                f"{resultado['cuentas_anonimizadas_retencion']} cuentas inactivas anonimizadas."
            )
        )
