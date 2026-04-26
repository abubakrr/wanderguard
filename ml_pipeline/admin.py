from django.contrib.gis import admin

from .models import LearnedPlace, TrainedModel, ZoneRiskCache


@admin.register(LearnedPlace)
class LearnedPlaceAdmin(admin.GISModelAdmin):
    list_display = ['patient', 'label', 'visit_count', 'avg_arrival_hour',
                    'avg_duration_minutes', 'radius_meters']
    list_filter = ['label', 'patient']
    readonly_fields = ['created_at']


@admin.register(TrainedModel)
class TrainedModelAdmin(admin.ModelAdmin):
    list_display = ['patient', 'model_type', 'training_points_count', 'training_date', 'is_active']
    list_filter = ['model_type', 'is_active', 'patient']
    readonly_fields = ['training_date']


@admin.register(ZoneRiskCache)
class ZoneRiskCacheAdmin(admin.ModelAdmin):
    list_display = ['grid_lat', 'grid_lng', 'risk_score', 'last_updated']
    ordering = ['-last_updated']
