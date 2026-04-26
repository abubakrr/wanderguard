from django.contrib.gis import admin

from .models import LocationPoint, StayPoint, Trip


@admin.register(LocationPoint)
class LocationPointAdmin(admin.GISModelAdmin):
    list_display = ['patient', 'timestamp', 'speed', 'accuracy', 'activity_type', 'is_anomaly']
    list_filter = ['activity_type', 'is_anomaly', 'patient']
    readonly_fields = ['created_at']
    ordering = ['-timestamp']


@admin.register(StayPoint)
class StayPointAdmin(admin.GISModelAdmin):
    list_display = ['patient', 'arrival_time', 'duration_minutes', 'radius_meters', 'point_count']
    list_filter = ['patient']
    readonly_fields = ['created_at']


@admin.register(Trip)
class TripAdmin(admin.GISModelAdmin):
    list_display = ['patient', 'start_time', 'distance_meters', 'avg_speed', 'path_to_displacement_ratio']
    list_filter = ['patient']
    readonly_fields = ['created_at']
