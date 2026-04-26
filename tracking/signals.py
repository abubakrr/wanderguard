from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LocationPoint


@receiver(post_save, sender=LocationPoint)
def on_location_saved(sender, instance, created, **kwargs):
    """Fire real-time processing task whenever a new GPS point is saved."""
    if created:
        from .tasks import process_location
        process_location.delay(instance.pk)
