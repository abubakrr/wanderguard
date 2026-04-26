from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import PatientProfile

from .models import LocationPoint
from .serializers import BatchLocationSerializer, LocationPointSerializer

User = get_user_model()


class LocationCreateView(APIView):
    """Patient app posts a single GPS point."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LocationPointSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(patient=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class LocationBatchView(APIView):
    """Patient app posts a batch of GPS points (offline sync)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = BatchLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        points_data = serializer.validated_data['points']
        created = []
        for point_data in points_data:
            lat = point_data.pop('lat')
            lng = point_data.pop('lng')
            from django.contrib.gis.geos import Point
            point_data['point'] = Point(lng, lat, srid=4326)
            created.append(LocationPoint(patient=request.user, **point_data))

        LocationPoint.objects.bulk_create(created)
        return Response({'saved': len(created)}, status=status.HTTP_201_CREATED)


def _assert_caregiver_access(caregiver, patient_id):
    """Returns patient User if caregiver is linked, else raises 403."""
    patient = get_object_or_404(User, pk=patient_id, role='patient')
    linked = PatientProfile.objects.filter(user=patient, caregiver=caregiver).exists()
    if not linked:
        return None, Response({'detail': 'Access denied.'}, status=403)
    return patient, None


class LatestLocationView(APIView):
    """Returns the most recent GPS point for a patient."""

    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):
        patient, err = _assert_caregiver_access(request.user, patient_id)
        if err:
            return err

        point = LocationPoint.objects.filter(patient=patient).first()
        if not point:
            return Response({'detail': 'No location data yet.'}, status=404)

        return Response(LocationPointSerializer(point).data)


class LocationHistoryView(APIView):
    """Returns paginated location history for a patient, with optional date range."""

    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):
        patient, err = _assert_caregiver_access(request.user, patient_id)
        if err:
            return err

        qs = LocationPoint.objects.filter(patient=patient)

        from_ts = request.query_params.get('from')
        to_ts = request.query_params.get('to')
        if from_ts:
            qs = qs.filter(timestamp__gte=from_ts)
        if to_ts:
            qs = qs.filter(timestamp__lte=to_ts)

        paginator = PageNumberPagination()
        paginator.page_size = 200
        page = paginator.paginate_queryset(qs, request)
        serializer = LocationPointSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
