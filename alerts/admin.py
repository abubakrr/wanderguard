from django.contrib.gis import admin

from .models import Alert, DeviceToken, RiskScore


@admin.register(RiskScore)
class RiskScoreAdmin(admin.ModelAdmin):
    list_display = ['patient', 'risk_level', 'combined_score', 'anomaly_score', 'timestamp']
    list_filter = ['risk_level', 'patient']
    ordering = ['-timestamp']
    readonly_fields = ['created_at']


@admin.register(Alert)
class AlertAdmin(admin.GISModelAdmin):
    list_display = ['patient', 'caregiver', 'alert_type', 'is_read', 'is_resolved', 'created_at']
    list_filter = ['alert_type', 'is_read', 'is_resolved', 'patient']
    ordering = ['-created_at']


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'device_type', 'is_active', 'updated_at']
    list_filter = ['device_type', 'is_active']
