import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [('patient', 'Patient'), ('caregiver', 'Caregiver')]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=20, blank=True)
    link_code = models.CharField(max_length=12, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.link_code:
            self.link_code = uuid.uuid4().hex[:12].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.username} ({self.role})'


class PatientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='patient_profile')
    caregiver = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='patients'
    )
    date_of_birth = models.DateField(null=True, blank=True)
    medical_notes = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=20, blank=True)
    is_active_monitoring = models.BooleanField(default=True)

    def __str__(self):
        return f'Profile: {self.user.username}'
