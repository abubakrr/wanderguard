from django.conf import settings
from django.contrib.gis.db import models


class LearnedPlace(models.Model):
    LABEL_CHOICES = [
        ('home', 'Home'),
        ('frequent', 'Frequent'),
        ('occasional', 'Occasional'),
    ]

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='learned_places',
    )
    centroid = models.PointField(geography=True, srid=4326)
    radius_meters = models.FloatField()
    visit_count = models.IntegerField()
    avg_arrival_hour = models.FloatField()
    avg_departure_hour = models.FloatField()
    avg_duration_minutes = models.FloatField()
    days_of_week = models.JSONField(default=list)   # e.g. [0, 1, 2, 3, 4]
    label = models.CharField(max_length=30, choices=LABEL_CHOICES, default='frequent')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-visit_count']

    def __str__(self):
        return f'LearnedPlace({self.patient.username}, {self.label}, visits={self.visit_count})'


class TrainedModel(models.Model):
    MODEL_TYPES = [
        ('isolation_forest', 'Isolation Forest'),
        ('threshold', 'Threshold Baseline'),
    ]

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trained_models',
    )
    model_type = models.CharField(max_length=30, choices=MODEL_TYPES)
    model_path = models.CharField(max_length=255)
    training_points_count = models.IntegerField()
    training_date = models.DateTimeField(auto_now_add=True)
    metrics = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-training_date']

    def __str__(self):
        return f'TrainedModel({self.patient.username}, {self.model_type}, active={self.is_active})'
