from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from tracking.preprocessing import run_preprocessing

User = get_user_model()


class Command(BaseCommand):
    help = 'Run preprocessing pipeline (noise filter → stay points → trips) for a patient'

    def add_arguments(self, parser):
        parser.add_argument('patient_id', type=int)

    def handle(self, *args, **options):
        try:
            patient = User.objects.get(pk=options['patient_id'], role='patient')
        except User.DoesNotExist:
            raise CommandError(f"No patient with id={options['patient_id']}")

        self.stdout.write(f'Preprocessing data for {patient.username}...')

        result = run_preprocessing(patient, logger=self.stdout.write)

        self.stdout.write(self.style.SUCCESS(
            f'\nDone!\n'
            f"  Clean points : {result['clean_points']:,}\n"
            f"  Stay points  : {result['stay_points']}\n"
            f"  Trips        : {result['trips']}"
        ))
