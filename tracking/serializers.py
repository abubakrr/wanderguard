from django.contrib.gis.geos import Point
from rest_framework import serializers

from .models import LocationPoint


class LocationPointSerializer(serializers.ModelSerializer):
    lat = serializers.FloatField(write_only=True)
    lng = serializers.FloatField(write_only=True)
    latitude = serializers.SerializerMethodField()
    longitude = serializers.SerializerMethodField()

    class Meta:
        model = LocationPoint
        fields = [
            'id', 'lat', 'lng', 'latitude', 'longitude',
            'speed', 'accuracy', 'battery_level', 'heading',
            'activity_type', 'timestamp', 'is_anomaly', 'anomaly_type',
        ]
        read_only_fields = ['id', 'latitude', 'longitude', 'is_anomaly', 'anomaly_type']

    def get_latitude(self, obj):
        return obj.point.y

    def get_longitude(self, obj):
        return obj.point.x

    def validate_accuracy(self, value):
        if value > 50:
            raise serializers.ValidationError('Accuracy too low (>50m). Point rejected.')
        return value

    def create(self, validated_data):
        lat = validated_data.pop('lat')
        lng = validated_data.pop('lng')
        validated_data['point'] = Point(lng, lat, srid=4326)
        return super().create(validated_data)


class BatchLocationSerializer(serializers.Serializer):
    points = LocationPointSerializer(many=True)
