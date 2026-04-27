from rest_framework import serializers
from .models import Alert, RiskScore


class RiskScoreSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiskScore
        fields = ['id', 'anomaly_score', 'zone_risk', 'time_factor',
                  'distance_factor', 'combined_score', 'risk_level', 'timestamp']


class AlertSerializer(serializers.ModelSerializer):
    patient_id      = serializers.SerializerMethodField()
    patient_name    = serializers.SerializerMethodField()
    risk_level      = serializers.SerializerMethodField()
    risk_score      = serializers.SerializerMethodField()
    anomaly_score   = serializers.SerializerMethodField()
    zone_risk       = serializers.SerializerMethodField()
    time_factor     = serializers.SerializerMethodField()
    distance_factor = serializers.SerializerMethodField()
    lat             = serializers.SerializerMethodField()
    lng             = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = [
            'id', 'patient_id', 'patient_name', 'alert_type', 'message',
            'risk_level', 'risk_score', 'anomaly_score', 'zone_risk',
            'time_factor', 'distance_factor',
            'lat', 'lng', 'is_read', 'is_resolved', 'created_at',
        ]

    def get_patient_id(self, obj):
        return obj.patient_id

    def get_patient_name(self, obj):
        return obj.patient.get_full_name() or obj.patient.username

    def get_risk_level(self, obj):
        return obj.risk_score.risk_level if obj.risk_score else 'unknown'

    def get_risk_score(self, obj):
        return obj.risk_score.combined_score if obj.risk_score else None

    def get_anomaly_score(self, obj):
        return obj.risk_score.anomaly_score if obj.risk_score else None

    def get_zone_risk(self, obj):
        return obj.risk_score.zone_risk if obj.risk_score else None

    def get_time_factor(self, obj):
        return obj.risk_score.time_factor if obj.risk_score else None

    def get_distance_factor(self, obj):
        return obj.risk_score.distance_factor if obj.risk_score else None

    def get_lat(self, obj):
        return obj.location.y if obj.location else None

    def get_lng(self, obj):
        return obj.location.x if obj.location else None
