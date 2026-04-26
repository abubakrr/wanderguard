from rest_framework import serializers
from .models import Alert, RiskScore


class RiskScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskScore
        fields = ['id', 'anomaly_score', 'zone_risk', 'time_factor',
                  'distance_factor', 'combined_score', 'risk_level', 'timestamp']


class AlertSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()
    risk_level = serializers.SerializerMethodField()
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = ['id', 'patient_name', 'alert_type', 'message', 'risk_level',
                  'lat', 'lng', 'is_read', 'is_resolved', 'created_at']

    def get_patient_name(self, obj):
        return obj.patient.get_full_name() or obj.patient.username

    def get_risk_level(self, obj):
        return obj.risk_score.risk_level if obj.risk_score else 'unknown'

    def get_lat(self, obj):
        return obj.location.y

    def get_lng(self, obj):
        return obj.location.x
