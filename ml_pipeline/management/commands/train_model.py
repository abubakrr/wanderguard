from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from ml_pipeline.training import train_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Train Isolation Forest anomaly detection model for a patient'

    def add_arguments(self, parser):
        parser.add_argument('patient_id', type=int)

    def handle(self, *args, **options):
        try:
            patient = User.objects.get(pk=options['patient_id'], role='patient')
        except User.DoesNotExist:
            raise CommandError(f"No patient with id={options['patient_id']}")

        self.stdout.write(f'Training model for {patient.username}...')
        metrics = train_model(patient, logger=self.stdout.write)

        if not metrics:
            self.stdout.write(self.style.WARNING('Training failed — no data.'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'\nIsolation Forest vs Threshold Baseline:\n'
            f"  {'Metric':<12} {'IF':>8} {'Baseline':>10}\n"
            f"  {'-'*32}\n"
            f"  {'Precision':<12} {metrics['precision']:>8.3f} {metrics['threshold_baseline']['precision']:>10.3f}\n"
            f"  {'Recall':<12} {metrics['recall']:>8.3f} {metrics['threshold_baseline']['recall']:>10.3f}\n"
            f"  {'F1':<12} {metrics['f1']:>8.3f} {metrics['threshold_baseline']['f1']:>10.3f}\n"
            f"  {'AUC':<12} {metrics['auc']:>8.3f} {'N/A':>10}"
        ))
