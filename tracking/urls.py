from django.urls import path

from .views import LatestLocationView, LocationBatchView, LocationCreateView, LocationHistoryView

urlpatterns = [
    path('tracking/location/', LocationCreateView.as_view(), name='location_create'),
    path('tracking/location/batch/', LocationBatchView.as_view(), name='location_batch'),
    path('tracking/location/latest/<int:patient_id>/', LatestLocationView.as_view(), name='location_latest'),
    path('tracking/location/history/<int:patient_id>/', LocationHistoryView.as_view(), name='location_history'),
]
