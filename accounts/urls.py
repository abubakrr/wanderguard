from django.urls import path
from drf_spectacular.utils import extend_schema
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import LinkPatientView, MeView, MyPatientsView, RegisterView

# Tag the simplejwt views so they appear under 'auth' in Swagger
TokenObtainPairView  = extend_schema(tags=['auth'])(TokenObtainPairView)
TokenRefreshView     = extend_schema(tags=['auth'])(TokenRefreshView)

urlpatterns = [
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', TokenObtainPairView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/me/', MeView.as_view(), name='me'),
    path('patients/link/', LinkPatientView.as_view(), name='link_patient'),
    path('patients/my-patients/', MyPatientsView.as_view(), name='my_patients'),
]
