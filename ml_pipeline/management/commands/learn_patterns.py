from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from ml_pipeline.pattern_learning import learn_patterns
from ml_pipeline.models import LearnedPlace

User = get_user_model()


class Command(BaseCommand):
    help = 'Run DBSCAN pattern learning on stay points for a patient'

    def add_arguments(self, parser):
        parser.add_argument('patient_id', type=int)

    def handle(self, *args, **options):
        try:
            patient = User.objects.get(pk=options['patient_id'], role='patient')
        except User.DoesNotExist:
            raise CommandError(f"No patient with id={options['patient_id']}")

        self.stdout.write(f'Learning patterns for {patient.username}...')
        places = learn_patterns(patient, logger=self.stdout.write)

        if not places:
            self.stdout.write(self.style.WARNING('No learned places created.'))
            return

        self.stdout.write(self.style.SUCCESS(f'\nLearned places ({len(places)}):'))
        for p in places:
            self.stdout.write(
                f'  [{p.label.upper():10s}] visits={p.visit_count:3d}  '
                f'avg_arrival={p.avg_arrival_hour:5.1f}h  '
                f'avg_dur={p.avg_duration_minutes:6.1f}min  '
                f'days={p.days_of_week}'
            )
