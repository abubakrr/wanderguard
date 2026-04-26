from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import PatientProfile
from tracking.models import LocationPoint
from tracking.serializers import LocationPointSerializer

from .models import Alert, RiskScore
from .notifications import register_device_token
from .serializers import AlertSerializer, RiskScoreSerializer

User = get_user_model()


def _caregiver_patients(caregiver):
    return User.objects.filter(
        patient_profile__caregiver=caregiver, role='patient'
    )


def _assert_owns_patient(caregiver, patient_id):
    patient = get_object_or_404(User, pk=patient_id, role='patient')
    if not PatientProfile.objects.filter(user=patient, caregiver=caregiver).exists():
        return None, Response({'detail': 'Access denied.'}, status=403)
    return patient, None


# ── Device token ───────────────────────────────────────────────────────────────

class RegisterDeviceTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get('token')
        device_type = request.data.get('device_type', 'android')
        if not token:
            return Response({'detail': 'token is required.'}, status=400)
        register_device_token(request.user, token, device_type)
        return Response({'detail': 'Token registered.'})


# ── Patient overview ───────────────────────────────────────────────────────────

class PatientOverviewView(APIView):
    """Quick-glance card: name, latest location, current risk, last update."""
    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):
        patient, err = _assert_owns_patient(request.user, patient_id)
        if err:
            return err

        latest_point = LocationPoint.objects.filter(patient=patient).first()
        latest_risk = RiskScore.objects.filter(patient=patient).first()

        return Response({
            'patient_id': patient.pk,
            'name': patient.get_full_name() or patient.username,
            'latest_location': LocationPointSerializer(latest_point).data if latest_point else None,
            'risk_level': latest_risk.risk_level if latest_risk else 'unknown',
            'risk_score': latest_risk.combined_score if latest_risk else None,
            'last_update': latest_point.timestamp if latest_point else None,
        })


# ── Risk history ───────────────────────────────────────────────────────────────

class RiskHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):
        patient, err = _assert_owns_patient(request.user, patient_id)
        if err:
            return err

        qs = RiskScore.objects.filter(patient=patient)
        from_ts = request.query_params.get('from')
        to_ts = request.query_params.get('to')
        if from_ts:
            qs = qs.filter(timestamp__gte=from_ts)
        if to_ts:
            qs = qs.filter(timestamp__lte=to_ts)

        paginator = PageNumberPagination()
        paginator.page_size = 100
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(RiskScoreSerializer(page, many=True).data)


# ── Alerts ─────────────────────────────────────────────────────────────────────

class AlertListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Alert.objects.filter(caregiver=request.user).select_related(
            'patient', 'risk_score'
        )
        unread_only = request.query_params.get('unread') == '1'
        if unread_only:
            qs = qs.filter(is_read=False)

        paginator = PageNumberPagination()
        paginator.page_size = 50
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(AlertSerializer(page, many=True).data)


class AlertUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Alert.objects.filter(caregiver=request.user, is_read=False).count()
        return Response({'unread': count})


class AlertResolveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, alert_id):
        alert = get_object_or_404(Alert, pk=alert_id, caregiver=request.user)
        alert.is_read = True
        alert.is_resolved = True
        alert.save(update_fields=['is_read', 'is_resolved'])
        return Response({'detail': 'Alert resolved.'})


# ── Heatmap ────────────────────────────────────────────────────────────────────

class HeatmapView(APIView):
    """Returns lat/lng/weight for heatmap visualisation."""
    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):
        patient, err = _assert_owns_patient(request.user, patient_id)
        if err:
            return err

        points = (
            LocationPoint.objects
            .filter(patient=patient)
            .values_list('point', 'is_anomaly')
            .order_by('-timestamp')[:2000]
        )
        data = [
            {'lat': p.y, 'lng': p.x, 'weight': 2.0 if anomaly else 1.0}
            for p, anomaly in points
        ]
        return Response(data)


# ── Learned places ─────────────────────────────────────────────────────────────

class LearnedPlacesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, patient_id):
        patient, err = _assert_owns_patient(request.user, patient_id)
        if err:
            return err

        from ml_pipeline.models import LearnedPlace
        places = LearnedPlace.objects.filter(patient=patient)
        data = [
            {
                'id': p.pk,
                'label': p.label,
                'lat': p.centroid.y,
                'lng': p.centroid.x,
                'radius_meters': p.radius_meters,
                'visit_count': p.visit_count,
                'avg_arrival_hour': p.avg_arrival_hour,
                'avg_duration_minutes': p.avg_duration_minutes,
                'days_of_week': p.days_of_week,
            }
            for p in places
        ]
        return Response(data)


# ── SOS alert ─────────────────────────────────────────────────────────────────

class SOSAlertView(APIView):
    """Patient triggers an immediate CRITICAL SOS alert."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.contrib.gis.geos import Point
        lat = request.data.get('lat')
        lng = request.data.get('lng')
        if lat is None or lng is None:
            return Response({'detail': 'lat and lng required.'}, status=400)

        profile = PatientProfile.objects.filter(
            user=request.user
        ).select_related('caregiver').first()
        if not profile or not profile.caregiver:
            return Response({'detail': 'No caregiver linked.'}, status=400)

        from .models import Alert
        alert = Alert.objects.create(
            patient=request.user,
            caregiver=profile.caregiver,
            alert_type='sos',
            message=f'SOS triggered by {request.user.get_full_name() or request.user.username}.',
            location=Point(float(lng), float(lat), srid=4326),
        )

        from .notifications import send_alert_notification
        # Create a minimal risk score stub for the notification helper
        alert.risk_score = type('obj', (object,), {
            'risk_level': 'critical', 'combined_score': 1.0
        })()
        send_alert_notification(alert)

        return Response({'detail': 'SOS alert sent.'}, status=status.HTTP_201_CREATED)
