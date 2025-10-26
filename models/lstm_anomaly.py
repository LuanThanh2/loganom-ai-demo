"""LSTM Autoencoder for time-series anomaly detection.

Notes:
- Uses TensorFlow/Keras if available. If not installed, raises a clear error.
- Trains on feature vectors ordered by time; outputs a joblib payload compatible with the repo style.
"""

from pathlib import Path
from typing import Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd

from models.utils import get_paths, load_models_config, ensure_dir


def _safe_import_tf():
    try:
        import tensorflow as tf  # type: ignore
        from tensorflow.keras.models import Sequential  # type: ignore
        from tensorflow.keras.layers import LSTM, Dense, Dropout, RepeatVector, TimeDistributed  # type: ignore
        from tensorflow.keras.optimizers import Adam  # type: ignore
        return tf, Sequential, LSTM, Dense, Dropout, RepeatVector, TimeDistributed, Adam
    except Exception as e:
        raise RuntimeError(
            "TensorFlow/Keras not installed. Please install with: pip install tensorflow keras"
        ) from e


class LSTMAutoencoderModel:
    def __init__(
        self,
        sequence_length: int,
        num_features: int,
        learning_rate: float = 1e-3,
        lstm_units: Tuple[int, int] = (64, 32),
        dropout: float = 0.2,
    ) -> None:
        (
            self._tf,
            self._Sequential,
            self._LSTM,
            self._Dense,
            self._Dropout,
            self._RepeatVector,
            self._TimeDistributed,
            self._Adam,
        ) = _safe_import_tf()
        self.sequence_length = sequence_length
        self.num_features = num_features
        self.learning_rate = learning_rate
        self.lstm_units = lstm_units
        self.dropout = dropout
        self.model = self._build_model()

    def _build_model(self):
        # Sequence-to-sequence autoencoder: encoder -> bottleneck -> repeat -> decoder -> timestep outputs
        m = self._Sequential(
            [
                # Encoder
                self._LSTM(self.lstm_units[0], return_sequences=True, input_shape=(self.sequence_length, self.num_features)),
                self._Dropout(self.dropout),
                self._LSTM(self.lstm_units[1], return_sequences=False),
                self._Dropout(self.dropout),
                # Repeat bottleneck across sequence length
                self._RepeatVector(self.sequence_length),
                # Decoder
                self._LSTM(self.lstm_units[1], return_sequences=True),
                self._Dropout(self.dropout),
                self._LSTM(self.lstm_units[0], return_sequences=True),
                self._Dropout(self.dropout),
                self._TimeDistributed(self._Dense(self.num_features, activation="linear")),
            ]
        )
        m.compile(optimizer=self._Adam(learning_rate=self.learning_rate), loss="mse")
        return m

    def make_sequences(self, X: np.ndarray) -> np.ndarray:
        if len(X) < self.sequence_length:
            return np.empty((0, self.sequence_length, X.shape[1]))
        out = []
        for i in range(len(X) - self.sequence_length + 1):
            out.append(X[i : i + self.sequence_length])
        return np.asarray(out)

    def fit(self, X: np.ndarray, epochs: int, batch_size: int, validation_split: float = 0.1) -> None:
        seq = self.make_sequences(X)
        if seq.size == 0:
            raise RuntimeError("Not enough rows to build sequences for LSTM.")
        self.model.fit(seq, seq, epochs=epochs, batch_size=batch_size, validation_split=validation_split, verbose=0)

    def reconstruction_mse(self, X: np.ndarray) -> np.ndarray:
        seq = self.make_sequences(X)
        preds = self.model.predict(seq, verbose=0)
        mse = np.mean((seq - preds) ** 2, axis=(1, 2))
        return mse

    # --- Custom pickling to avoid serializing TF modules ---
    def __getstate__(self):
        return {
            "_pickled_version": 1,
            "sequence_length": self.sequence_length,
            "num_features": self.num_features,
            "learning_rate": self.learning_rate,
            "lstm_units": self.lstm_units,
            "dropout": self.dropout,
            # Store raw weights (list of numpy arrays)
            "weights": self.model.get_weights() if hasattr(self, "model") else None,
        }

    def __setstate__(self, state):
        # Restore simple attributes
        self.sequence_length = int(state.get("sequence_length", 10))
        self.num_features = int(state.get("num_features", 1))
        self.learning_rate = float(state.get("learning_rate", 1e-3))
        self.lstm_units = tuple(state.get("lstm_units", (64, 32)))  # type: ignore
        self.dropout = float(state.get("dropout", 0.2))

        # Re-import TF symbols and rebuild model
        (
            self._tf,
            self._Sequential,
            self._LSTM,
            self._Dense,
            self._Dropout,
            self._RepeatVector,
            self._TimeDistributed,
            self._Adam,
        ) = _safe_import_tf()

        self.model = self._build_model()
        weights = state.get("weights")
        if weights is not None:
            try:
                self.model.set_weights(weights)
            except Exception:
                # If weights mismatch (e.g., different config), ignore to allow loading
                pass


def _select_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    id_cols = {"@timestamp", "host.name", "user.name", "source.ip", "destination.ip", "session.id"}
    feature_cols = [c for c in df.columns if c not in id_cols and pd.api.types.is_numeric_dtype(df[c])]
    X = df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return X, feature_cols


def train_lstm_model() -> Path:
    paths = get_paths()
    cfg = load_models_config()

    feat_path = Path(paths["features_dir"]) / "features.parquet"
    df = pd.read_parquet(feat_path)
    if df.empty:
        raise RuntimeError("Feature table is empty; run featurize first")

    # Sort by time to maintain temporal order
    if "@timestamp" in df.columns:
        df["@timestamp"] = pd.to_datetime(df["@timestamp"], utc=True, errors="coerce")
        df = df.dropna(subset=["@timestamp"]).sort_values("@timestamp")

    # Optional RAM-friendly sampling (controlled via env):
    # - LSTM_MAX_ROWS: cap total rows used for training
    # - LSTM_SAMPLE_FRAC: alternative fractional sample (0<frac<=1)
    import os
    try:
        max_rows = int(os.getenv("LSTM_MAX_ROWS", "0"))
    except Exception:
        max_rows = 0
    try:
        sample_frac = float(os.getenv("LSTM_SAMPLE_FRAC", "0"))
    except Exception:
        sample_frac = 0.0
    if sample_frac > 0 and sample_frac < 1:
        df = df.sample(frac=sample_frac, random_state=42).sort_values("@timestamp")
    elif max_rows > 0 and len(df) > max_rows:
        df = df.sample(n=max_rows, random_state=42).sort_values("@timestamp")

    X, feature_cols = _select_features(df)

    # Config defaults with optional YAML overrides
    lstm_cfg: Dict = cfg.get("lstm_autoencoder", {}) if isinstance(cfg, dict) else {}
    seq_len = int(lstm_cfg.get("sequence_length", 60))
    epochs = int(lstm_cfg.get("epochs", 30))
    batch_size = int(lstm_cfg.get("batch_size", 32))
    lr = float(lstm_cfg.get("learning_rate", 1e-3))
    units = lstm_cfg.get("lstm_units", [64, 32])
    dropout = float(lstm_cfg.get("dropout", 0.2))

    # Allow environment overrides for quick, low-RAM runs
    try:
        seq_len = int(os.getenv("LSTM_SEQ_LEN", str(seq_len)))
    except Exception:
        pass
    try:
        epochs = int(os.getenv("LSTM_EPOCHS", str(epochs)))
    except Exception:
        pass
    try:
        batch_size = int(os.getenv("LSTM_BATCH_SIZE", str(batch_size)))
    except Exception:
        pass

    model = LSTMAutoencoderModel(
        sequence_length=seq_len,
        num_features=X.shape[1],
        learning_rate=lr,
        lstm_units=(int(units[0]), int(units[1]) if len(units) > 1 else int(units[0]) // 2),
        dropout=dropout,
    )
    model.fit(X.values, epochs=epochs, batch_size=batch_size)

    out_dir = Path(paths["models_dir"]).resolve()
    ensure_dir(out_dir)
    out_path = out_dir / "lstm_anomaly.joblib"
    payload = {
        "model_type": "LSTM_AE",
        "model": model,
        "feature_cols": feature_cols,
        "meta": {
            "sequence_length": seq_len,
            "epochs": epochs,
            "batch_size": batch_size,
            "learning_rate": lr,
            "lstm_units": units,
            "dropout": dropout,
        },
    }
    joblib.dump(payload, out_path)
    return out_path


if __name__ == "__main__":
    train_lstm_model()


