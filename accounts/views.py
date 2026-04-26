from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import PatientProfile
from .serializers import (
    LinkPatientSerializer,
    PatientProfileSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response(
            {
                'user': UserSerializer(user).data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class LinkPatientView(APIView):
    """Caregiver links themselves to a patient via the patient's link_code."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 'caregiver':
            return Response({'detail': 'Only caregivers can link patients.'}, status=403)

        serializer = LinkPatientSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data['link_code']

        try:
            patient = User.objects.get(link_code=code, role='patient')
        except User.DoesNotExist:
            return Response({'detail': 'Invalid link code.'}, status=404)

        profile, _ = PatientProfile.objects.get_or_create(user=patient)
        profile.caregiver = request.user
        profile.save()

        return Response({'detail': f'Linked to patient {patient.username}.'})


class MyPatientsView(APIView):
    """Returns all patients linked to the authenticated caregiver."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'caregiver':
            return Response({'detail': 'Only caregivers can view patients.'}, status=403)

        profiles = PatientProfile.objects.filter(caregiver=request.user).select_related('user')
        return Response(PatientProfileSerializer(profiles, many=True).data)
