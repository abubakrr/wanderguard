from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .notifications import register_device_token


class RegisterDeviceTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.data.get('token')
        device_type = request.data.get('device_type', 'android')
        if not token:
            return Response({'detail': 'token is required.'}, status=400)
        register_device_token(request.user, token, device_type)
        return Response({'detail': 'Token registered.'})
