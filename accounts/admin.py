from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import PatientProfile, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('WanderGuard', {'fields': ('role', 'phone', 'link_code')}),
    )
    list_display = ['username', 'email', 'role', 'link_code', 'is_staff']
    list_filter = ['role'] + list(UserAdmin.list_filter)


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'caregiver', 'is_active_monitoring']
    list_filter = ['is_active_monitoring']
