from django.conf import settings
from django.contrib.gis.db import models

from tracking.models import LocationPoint


class RiskScore(models.Model):
    LEVEL_CHOICES = [
        ('safe', 'Safe'),
        ('caution', 'Caution'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ]

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='risk_scores'
    )
    location = models.ForeignKey(LocationPoint, on_delete=models.CASCADE, related_name='risk_scores')
    anomaly_score = models.FloatField()
    zone_risk = models.FloatField()
    time_factor = models.FloatField()
    distance_factor = models.FloatField()
    combined_score = models.FloatField()
    risk_level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [models.Index(fields=['patient', '-timestamp'])]

    def __str__(self):
        return f'RiskScore({self.patient.username}, {self.risk_level}, {self.combined_score:.2f})'


class Alert(models.Model):
    ALERT_TYPES = [
        ('wandering', 'Wandering'),
        ('deviation', 'Deviation'),
        ('unfamiliar', 'Unfamiliar Location'),
        ('aimless', 'Aimless Movement'),
        ('sos', 'SOS'),
        ('general', 'General'),
    ]

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='patient_alerts'
    )
    caregiver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='caregiver_alerts'
    )
    risk_score = models.ForeignKey(
        RiskScore, on_delete=models.CASCADE, related_name='alerts', null=True, blank=True
    )
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES, default='general')
    message = models.TextField()
    location = models.PointField(geography=True, srid=4326)
    is_read = models.BooleanField(default=False)
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['caregiver', '-created_at'])]

    def __str__(self):
        return f'Alert({self.patient.username} → {self.caregiver.username}, {self.alert_type})'
