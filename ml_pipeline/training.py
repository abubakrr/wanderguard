"""
Isolation Forest training pipeline.
Callable directly or via: python manage.py train_model <patient_id>
"""

import os

import joblib
import numpy as np
from django.conf import settings
from sklearn.ensemble import IsolationForest
from sklearn.metrics import classification_report, f1_score, precision_score, recall_score, roc_auc_score

from tracking.models import LocationPoint
from .features import FEATURE_NAMES, compute_features_batch
from .models import TrainedModel

MODELS_DIR = os.path.join(settings.BASE_DIR, 'models')


def _model_path(patient_id, model_type):
    os.makedirs(MODELS_DIR, exist_ok=True)
    return os.path.join(MODELS_DIR, f'patient_{patient_id}_{model_type}.joblib')


def train_model(patient, logger=None):
    """
    Train Isolation Forest on normal points only.
    Evaluates against all points (normal + anomaly) using ground-truth labels.
    Returns dict of metrics.
    """
    def log(msg):
        if logger:
            logger(msg)

    all_points = list(LocationPoint.objects.filter(patient=patient).order_by('timestamp'))
    if not all_points:
        log('  No location points found.')
        return {}

    log(f'  Computing features for {len(all_points):,} points...')
    X_all, points = compute_features_batch(patient, points=all_points)
    y_true = np.array([1 if p.is_anomaly else 0 for p in points])

    # Train on normal points only
    normal_mask = y_true == 0
    X_train = X_all[normal_mask]
    log(f'  Training on {X_train.shape[0]:,} normal points ({X_all.shape[0] - X_train.shape[0]} anomalies held out)...')

    model = IsolationForest(n_estimators=100, contamination=0.08, random_state=42)
    model.fit(X_train)

    # Score all points — normalize decision_function to [0, 1] anomaly score
    raw = model.decision_function(X_all)
    scores = 1 - (raw - raw.min()) / (raw.max() - raw.min() + 1e-9)
    y_pred = (scores >= 0.5).astype(int)

    metrics = _compute_metrics(y_true, y_pred, scores)
    metrics['threshold_baseline'] = _threshold_baseline_metrics(X_all, y_true, FEATURE_NAMES)

    log(f"  IF    → P={metrics['precision']:.3f}  R={metrics['recall']:.3f}  F1={metrics['f1']:.3f}  AUC={metrics['auc']:.3f}")
    log(f"  Base  → P={metrics['threshold_baseline']['precision']:.3f}  "
        f"R={metrics['threshold_baseline']['recall']:.3f}  "
        f"F1={metrics['threshold_baseline']['f1']:.3f}")

    # Save model
    path = _model_path(patient.pk, 'isolation_forest')
    joblib.dump({'model': model, 'raw_min': float(raw.min()), 'raw_max': float(raw.max())}, path)

    # Deactivate old records, save new
    TrainedModel.objects.filter(patient=patient, model_type='isolation_forest').update(is_active=False)
    TrainedModel.objects.create(
        patient=patient,
        model_type='isolation_forest',
        model_path=path,
        training_points_count=X_train.shape[0],
        metrics=metrics,
        is_active=True,
    )

    log(f'  Model saved to {path}')
    return metrics


def load_model(patient):
    """Load the active Isolation Forest for a patient. Returns (model_dict, TrainedModel) or (None, None)."""
    record = TrainedModel.objects.filter(
        patient=patient, model_type='isolation_forest', is_active=True
    ).first()
    if not record or not os.path.exists(record.model_path):
        return None, None
    return joblib.load(record.model_path), record


def score_point(patient, point, model_dict=None):
    """
    Return anomaly score [0, 1] for a single LocationPoint.
    Loads model from disk if model_dict not provided.
    """
    if model_dict is None:
        model_dict, _ = load_model(patient)
    if model_dict is None:
        return 0.5   # no model yet → neutral score

    from .features import compute_features, PatientContext
    ctx = PatientContext(patient)
    f = compute_features(patient, point, ctx=ctx)
    X = np.array([[f[name] for name in FEATURE_NAMES]])

    raw = model_dict['model'].decision_function(X)[0]
    raw_min, raw_max = model_dict['raw_min'], model_dict['raw_max']
    score = 1 - (raw - raw_min) / (raw_max - raw_min + 1e-9)
    return float(np.clip(score, 0.0, 1.0))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _compute_metrics(y_true, y_pred, scores):
    return {
        'precision': round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        'recall':    round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        'f1':        round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        'auc':       round(float(roc_auc_score(y_true, scores)), 4),
    }


def _threshold_baseline_metrics(X_all, y_true, feature_names):
    """Simple threshold baseline: flag if distance_from_home > 500m."""
    idx = feature_names.index('distance_from_home')
    y_pred = (X_all[:, idx] > 500).astype(int)
    return {
        'precision': round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        'recall':    round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        'f1':        round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
    }
