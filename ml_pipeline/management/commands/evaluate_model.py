"""
Evaluation command: python manage.py evaluate_model <patient_id>

Computes all thesis Chapter 4 metrics:
  1. Precision, Recall, F1 — overall and per anomaly type
  2. ROC curve + AUC
  3. Confusion matrix
  4. Isolation Forest vs geofence vs threshold baselines
  5. Inference time per point
  6. Feature importance (permutation-based ablation)

Saves JSON metrics + PNG charts to evaluation/<patient_id>/
"""

import json
import os
import time

import numpy as np
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

from ml_pipeline.features import FEATURE_NAMES, compute_features_batch
from ml_pipeline.training import load_model
from tracking.models import LocationPoint

User = get_user_model()


class Command(BaseCommand):
    help = 'Evaluate anomaly detection model and produce thesis metrics + charts'

    def add_arguments(self, parser):
        parser.add_argument('patient_id', type=int)

    def handle(self, *args, **options):
        try:
            patient = User.objects.get(pk=options['patient_id'], role='patient')
        except User.DoesNotExist:
            raise CommandError(f"No patient with id={options['patient_id']}")

        model_dict, record = load_model(patient)
        if model_dict is None:
            raise CommandError('No trained model found. Run train_model first.')

        out_dir = os.path.join('evaluation', str(patient.pk))
        os.makedirs(out_dir, exist_ok=True)

        self.stdout.write(f'Evaluating model for {patient.username}...')

        # ── Load data ──────────────────────────────────────────────────────────
        all_points = list(LocationPoint.objects.filter(patient=patient).order_by('timestamp'))
        self.stdout.write(f'  Computing features for {len(all_points):,} points...')
        X_all, points = compute_features_batch(patient, points=all_points)
        y_true = np.array([1 if p.is_anomaly else 0 for p in points])
        anomaly_types = [p.anomaly_type for p in points]

        # ── Isolation Forest scores ────────────────────────────────────────────
        raw = model_dict['model'].decision_function(X_all)
        scores = 1 - (raw - model_dict['raw_min']) / (model_dict['raw_max'] - model_dict['raw_min'] + 1e-9)
        scores = np.clip(scores, 0, 1)
        y_pred = (scores >= 0.5).astype(int)

        # ── 1. Overall metrics ─────────────────────────────────────────────────
        overall = {
            'precision': round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
            'recall':    round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
            'f1':        round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
            'auc':       round(float(roc_auc_score(y_true, scores)), 4),
            'total_points': len(points),
            'anomaly_points': int(y_true.sum()),
        }
        self.stdout.write(f"  Overall → P={overall['precision']}  R={overall['recall']}  F1={overall['f1']}  AUC={overall['auc']}")

        # ── 2. Per-anomaly-type metrics ────────────────────────────────────────
        per_type = {}
        for atype in ['WANDERING', 'DEVIATION', 'UNFAMILIAR', 'AIMLESS']:
            mask = np.array([t == atype for t in anomaly_types])
            if mask.sum() == 0:
                continue
            y_t = mask.astype(int)
            y_p = y_pred.copy()
            per_type[atype] = {
                'precision': round(float(precision_score(y_t, y_p, zero_division=0)), 4),
                'recall':    round(float(recall_score(y_t, y_p, zero_division=0)), 4),
                'f1':        round(float(f1_score(y_t, y_p, zero_division=0)), 4),
                'count':     int(mask.sum()),
            }
            self.stdout.write(
                f"  {atype:<12} → P={per_type[atype]['precision']}  R={per_type[atype]['recall']}  F1={per_type[atype]['f1']}  n={per_type[atype]['count']}"
            )

        # ── 3. Baseline comparisons ────────────────────────────────────────────
        geofence_y = (X_all[:, FEATURE_NAMES.index('distance_from_home')] > 200).astype(int)
        threshold_y = (X_all[:, FEATURE_NAMES.index('distance_from_home')] > 500).astype(int)
        baselines = {
            'geofence_200m': {
                'precision': round(float(precision_score(y_true, geofence_y, zero_division=0)), 4),
                'recall':    round(float(recall_score(y_true, geofence_y, zero_division=0)), 4),
                'f1':        round(float(f1_score(y_true, geofence_y, zero_division=0)), 4),
            },
            'threshold_500m': {
                'precision': round(float(precision_score(y_true, threshold_y, zero_division=0)), 4),
                'recall':    round(float(recall_score(y_true, threshold_y, zero_division=0)), 4),
                'f1':        round(float(f1_score(y_true, threshold_y, zero_division=0)), 4),
            },
        }

        # ── 4. Inference time ──────────────────────────────────────────────────
        sample = X_all[:100]
        start = time.perf_counter()
        for _ in range(100):
            model_dict['model'].decision_function(sample)
        elapsed = (time.perf_counter() - start) / (100 * 100) * 1000
        inference_ms = round(elapsed, 3)
        self.stdout.write(f'  Inference time: {inference_ms} ms/point')

        # ── 5. Feature importance (permutation ablation) ───────────────────────
        baseline_f1 = overall['f1']
        importance = {}
        for i, fname in enumerate(FEATURE_NAMES):
            X_perm = X_all.copy()
            np.random.shuffle(X_perm[:, i])
            raw_p = model_dict['model'].decision_function(X_perm)
            scores_p = np.clip(1 - (raw_p - model_dict['raw_min']) / (model_dict['raw_max'] - model_dict['raw_min'] + 1e-9), 0, 1)
            y_p = (scores_p >= 0.5).astype(int)
            perm_f1 = float(f1_score(y_true, y_p, zero_division=0))
            importance[fname] = round(baseline_f1 - perm_f1, 4)
        importance_sorted = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

        # ── Save JSON ──────────────────────────────────────────────────────────
        results = {
            'overall': overall,
            'per_anomaly_type': per_type,
            'baselines': baselines,
            'inference_ms_per_point': inference_ms,
            'feature_importance': importance_sorted,
        }
        json_path = os.path.join(out_dir, 'metrics.json')
        with open(json_path, 'w') as f:
            json.dump(results, f, indent=2)
        self.stdout.write(f'  Metrics saved → {json_path}')

        # ── Charts ─────────────────────────────────────────────────────────────
        self._plot_roc(y_true, scores, out_dir)
        self._plot_confusion(y_true, y_pred, out_dir)
        self._plot_feature_importance(importance_sorted, out_dir)

        self.stdout.write(self.style.SUCCESS(f'\nEvaluation complete. Output in {out_dir}/'))

    # ── Chart helpers ──────────────────────────────────────────────────────────

    def _plot_roc(self, y_true, scores, out_dir):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        fpr, tpr, _ = roc_curve(y_true, scores)
        auc = roc_auc_score(y_true, scores)

        fig, ax = plt.subplots(figsize=(6, 5))
        ax.plot(fpr, tpr, lw=2, label=f'Isolation Forest (AUC={auc:.3f})')
        ax.plot([0, 1], [0, 1], 'k--', lw=1)
        ax.set_xlabel('False Positive Rate')
        ax.set_ylabel('True Positive Rate')
        ax.set_title('ROC Curve — WanderGuard Anomaly Detection')
        ax.legend()
        fig.tight_layout()
        path = os.path.join(out_dir, 'roc_curve.png')
        fig.savefig(path, dpi=150)
        plt.close(fig)
        self.stdout.write(f'  ROC curve → {path}')

    def _plot_confusion(self, y_true, y_pred, out_dir):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        cm = confusion_matrix(y_true, y_pred)
        disp = ConfusionMatrixDisplay(cm, display_labels=['Normal', 'Anomaly'])
        fig, ax = plt.subplots(figsize=(5, 4))
        disp.plot(ax=ax, colorbar=False)
        ax.set_title('Confusion Matrix')
        fig.tight_layout()
        path = os.path.join(out_dir, 'confusion_matrix.png')
        fig.savefig(path, dpi=150)
        plt.close(fig)
        self.stdout.write(f'  Confusion matrix → {path}')

    def _plot_feature_importance(self, importance, out_dir):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        names = list(importance.keys())
        values = list(importance.values())

        fig, ax = plt.subplots(figsize=(8, 5))
        bars = ax.barh(names[::-1], values[::-1])
        ax.set_xlabel('F1 drop when feature shuffled (higher = more important)')
        ax.set_title('Feature Importance (Permutation Ablation)')
        fig.tight_layout()
        path = os.path.join(out_dir, 'feature_importance.png')
        fig.savefig(path, dpi=150)
        plt.close(fig)
        self.stdout.write(f'  Feature importance → {path}')
