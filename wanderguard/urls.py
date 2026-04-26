from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

# ── Admin branding ─────────────────────────────────────────────────────────────
admin.site.site_header  = 'WanderGuard Admin'
admin.site.site_title   = 'WanderGuard'
admin.site.index_title  = 'System Administration'

urlpatterns = [
    # Django admin
    path('admin/', admin.site.urls),

    # OpenAPI schema (raw JSON)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),

    # Swagger UI
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # ReDoc (alternative docs)
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # App routes
    path('api/', include('accounts.urls')),
    path('api/', include('tracking.urls')),
    path('api/', include('alerts.urls')),
]
