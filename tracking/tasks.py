from celery import shared_task


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def process_location(self, point_id):
    """
    Full real-time pipeline for a single GPS point:
      features → Isolation Forest score → zone risk → risk score → alert → push
    """
    try:
        from django.contrib.auth import get_user_model
        from tracking.models import LocationPoint
        from ml_pipeline.training import load_model
        from alerts.risk_engine import compute_risk_score

        point = LocationPoint.objects.select_related('patient').get(pk=point_id)
        patient = point.patient

        model_dict, _ = load_model(patient)
        compute_risk_score(patient, point, model_dict=model_dict)

    except LocationPoint.DoesNotExist:
        pass   # point deleted before task ran — ignore
    except Exception as exc:
        raise self.retry(exc=exc)
