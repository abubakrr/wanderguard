from django.contrib.gis import admin

from .models import LearnedPlace


@admin.register(LearnedPlace)
class LearnedPlaceAdmin(admin.GISModelAdmin):
    list_display = ['patient', 'label', 'visit_count', 'avg_arrival_hour',
                    'avg_duration_minutes', 'radius_meters']
    list_filter = ['label', 'patient']
    readonly_fields = ['created_at']
