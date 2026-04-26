from django.conf import settings
from django.contrib.gis.db import models


class LocationPoint(models.Model):
    ACTIVITY_CHOICES = [
        ('still', 'Still'),
        ('walking', 'Walking'),
        ('running', 'Running'),
        ('in_vehicle', 'In Vehicle'),
        ('unknown', 'Unknown'),
    ]

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='locations',
    )
    point = models.PointField(geography=True, srid=4326)
    speed = models.FloatField(default=0)          # m/s
    accuracy = models.FloatField(default=0)       # meters
    battery_level = models.IntegerField(default=0)
    heading = models.FloatField(default=0)        # degrees
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_CHOICES, blank=True)
    timestamp = models.DateTimeField()

    # evaluation-only labels (set by synthetic data generator)
    is_anomaly = models.BooleanField(default=False)
    anomaly_type = models.CharField(max_length=30, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['patient', '-timestamp']),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.patient.username} @ {self.timestamp}'


class StayPoint(models.Model):
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='stay_points',
    )
    centroid = models.PointField(geography=True, srid=4326)
    radius_meters = models.FloatField()
    arrival_time = models.DateTimeField()
    departure_time = models.DateTimeField()
    duration_minutes = models.FloatField()
    point_count = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['patient', 'arrival_time'])]
        ordering = ['arrival_time']

    def __str__(self):
        return f'StayPoint({self.patient.username}, {self.arrival_time:%Y-%m-%d %H:%M}, {self.duration_minutes:.0f}min)'


class Trip(models.Model):
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trips',
    )
    start_point = models.PointField(geography=True, srid=4326)
    end_point = models.PointField(geography=True, srid=4326)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    distance_meters = models.FloatField()
    avg_speed = models.FloatField()
    point_count = models.IntegerField()
    path_to_displacement_ratio = models.FloatField(default=1.0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['patient', 'start_time'])]
        ordering = ['start_time']

    def __str__(self):
        return f'Trip({self.patient.username}, {self.start_time:%Y-%m-%d %H:%M}, {self.distance_meters:.0f}m)'
