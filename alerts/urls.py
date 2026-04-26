from django.urls import path
from .views import (
    AlertListView, AlertResolveView, AlertUnreadCountView,
    HeatmapView, LearnedPlacesView, PatientOverviewView,
    RegisterDeviceTokenView, RiskHistoryView, SOSAlertView,
)

urlpatterns = [
    path('device-token/', RegisterDeviceTokenView.as_view(), name='register_device_token'),
    path('alerts/sos/', SOSAlertView.as_view(), name='sos_alert'),
    path('alerts/', AlertListView.as_view(), name='alert_list'),
    path('alerts/unread-count/', AlertUnreadCountView.as_view(), name='alert_unread_count'),
    path('alerts/<int:alert_id>/resolve/', AlertResolveView.as_view(), name='alert_resolve'),
    path('patients/<int:patient_id>/overview/', PatientOverviewView.as_view(), name='patient_overview'),
    path('patients/<int:patient_id>/risk-history/', RiskHistoryView.as_view(), name='risk_history'),
    path('tracking/heatmap/<int:patient_id>/', HeatmapView.as_view(), name='heatmap'),
    path('ml/learned-places/<int:patient_id>/', LearnedPlacesView.as_view(), name='learned_places'),
]
