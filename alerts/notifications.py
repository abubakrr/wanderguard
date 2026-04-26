"""
Firebase Cloud Messaging push notification sender.

Setup: place your Firebase service account JSON at the path set in
FIREBASE_CREDENTIALS_PATH in settings.py (default: firebase-credentials.json).
If the file is absent, all sends are no-ops (safe for development).
"""

import logging
import os

from django.conf import settings

from .models import DeviceToken

logger = logging.getLogger(__name__)

_firebase_app = None


def _get_app():
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    creds_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', 'firebase-credentials.json')
    if not os.path.exists(creds_path):
        logger.warning('FCM: credentials file not found at %s — push disabled.', creds_path)
        return None

    import firebase_admin
    from firebase_admin import credentials
    cred = credentials.Certificate(creds_path)
    _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app


def send_alert_notification(alert):
    """
    Send a push notification to the caregiver's registered devices.
    Silently skips if Firebase is not configured or tokens are missing.
    """
    app = _get_app()
    if app is None:
        return

    tokens = list(
        DeviceToken.objects
        .filter(user=alert.caregiver, is_active=True)
        .values_list('token', flat=True)
    )
    if not tokens:
        return

    from firebase_admin import messaging

    patient_name = alert.patient.get_full_name() or alert.patient.username
    title = f'WanderGuard — {alert.risk_score.risk_level.upper()} alert'
    body = f'{patient_name}: {alert.message[:100]}'

    for token in tokens:
        try:
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data={
                    'alert_id': str(alert.pk),
                    'patient_id': str(alert.patient_id),
                    'risk_level': alert.risk_score.risk_level,
                    'alert_type': alert.alert_type,
                    'lat': str(alert.location.y),
                    'lng': str(alert.location.x),
                },
                token=token,
            )
            messaging.send(message, app=app)
        except Exception as exc:
            logger.error('FCM send failed for token %s: %s', token[:20], exc)
            DeviceToken.objects.filter(token=token).update(is_active=False)


def register_device_token(user, token, device_type='android'):
    """Register or refresh a device FCM token."""
    DeviceToken.objects.update_or_create(
        token=token,
        defaults={'user': user, 'device_type': device_type, 'is_active': True},
    )
