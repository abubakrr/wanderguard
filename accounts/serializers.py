from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import PatientProfile

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'role', 'phone']

    def validate_role(self, value):
        if value not in ('patient', 'caregiver'):
            raise serializers.ValidationError("Role must be 'patient' or 'caregiver'.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            role=validated_data['role'],
            phone=validated_data.get('phone', ''),
        )
        if user.role == 'patient':
            PatientProfile.objects.create(user=user)
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'phone', 'link_code']
        read_only_fields = ['id', 'link_code']


class PatientProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = PatientProfile
        fields = '__all__'


class LinkPatientSerializer(serializers.Serializer):
    link_code = serializers.CharField(max_length=12)
