from typing import Dict, List

import os
import numpy as np


def top_shap_for_rows(model, X, feature_names: List[str], top_k: int = 5) -> List[Dict]:
    # Try to import shap lazily with JIT disabled to avoid llvmlite/numba issues
    try:
        os.environ.setdefault("NUMBA_DISABLE_JIT", "1")
        os.environ.setdefault("SHAP_DISABLE_JIT", "1")
        import shap  # type: ignore

        try:
            explainer = shap.TreeExplainer(model)
            shap_values = explainer.shap_values(X)
            values = shap_values if isinstance(shap_values, np.ndarray) else shap_values.values
        except Exception:
            # KernelExplainer fallback (slower, but works on CPU and avoids tree specifics)
            explainer = shap.KernelExplainer(model.decision_function, X[: min(50, len(X))])
            values = explainer.shap_values(X, nsamples=50)

        if isinstance(values, list):
            values = values[0]

        out: List[Dict] = []
        for row_vals in values:
            idx = np.argsort(-np.abs(row_vals))[:top_k]
            features = [
                {"feature": feature_names[i], "value": float(row_vals[i])}
                for i in idx
            ]
            out.append({"top_features": features})
        return out

    except Exception:
        # Final fallback: rank features by absolute value in the row (not true SHAP)
        out: List[Dict] = []
        for row in X:
            idx = np.argsort(-np.abs(row))[:top_k]
            features = [
                {"feature": feature_names[i], "value": float(row[i])}
                for i in idx
            ]
            out.append({"top_features": features, "note": "fallback_no_shap"})
        return out
