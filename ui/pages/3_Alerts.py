import sys
import json
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import os
import joblib
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from datetime import datetime

from models.utils import get_paths
from pipeline.alerting import select_alerts
from pipeline.bundle import build_bundle_for_alert
from explain.shap_explain import top_shap_for_rows

st.title("Alerts")
paths = get_paths()

def _load_ai_from_bundle(bundle_zip: Path):
    data = None
    md = None
    if not bundle_zip.exists():
        return data, md
    try:
        with zipfile.ZipFile(bundle_zip, "r") as z:
            if "ai_analysis.json" in z.namelist():
                with z.open("ai_analysis.json") as f:
                    data = json.loads(f.read().decode("utf-8"))
            if "ai_analysis.md" in z.namelist():
                with z.open("ai_analysis.md") as f:
                    md = f.read().decode("utf-8")
    except Exception as e:
        st.warning(f"Không đọc được bundle: {e}")
    return data, md

scores_path = Path(paths["scores_dir"]) / "scores.parquet"
colA, colB = st.columns(2)
with colA:
    if st.button("Reload data"):
        st.experimental_rerun()
with colB:
    if scores_path.exists():
        mtime = datetime.fromtimestamp(os.path.getmtime(scores_path)).strftime("%Y-%m-%d %H:%M:%S")
        st.caption(f"scores.parquet last modified: {mtime}")
if not scores_path.exists():
    st.warning("Chưa có điểm bất thường. Chạy pipeline trước (ingest/featurize/train/score).")
    st.stop()

try:
    top, thr = select_alerts(str(scores_path))
except Exception as e:
    st.error(f"Lỗi chọn alerts: {e}")
    st.stop()

st.caption(f"Threshold: {thr:.4f}")
if top.empty:
    st.info("Chưa có alert vượt ngưỡng.")
    st.stop()

cols_show = [c for c in ["@timestamp","host.name","user.name","source.ip","destination.ip","anom.score"] if c in top.columns]
st.dataframe(top[cols_show], use_container_width=True, hide_index=True)

idx = st.number_input("Chọn alert (chỉ số hàng)", min_value=0, max_value=len(top)-1, value=0, step=1)
row = top.iloc[int(idx)]

st.subheader("Top SHAP Features")
names, vals = [], []
try:
    payload = joblib.load(Path(paths["models_dir"]) / "isolation_forest.joblib")
    model = payload["model"] if isinstance(payload, dict) and "model" in payload else payload
    feature_cols = payload.get("feature_cols") if isinstance(payload, dict) else None
    if not feature_cols:
        feature_cols = [c for c in row.index if isinstance(row[c], (int,float))]
    X = row[feature_cols].fillna(0.0).to_frame().T
    shap_info = top_shap_for_rows(model, X.values, feature_cols, top_k=5)[0]
    feats = shap_info.get("top_features", [])
    names = [f.get("feature","") for f in feats]
    vals = [f.get("value",0.0) for f in feats]
except Exception as e:
    st.caption(f"Không tính được SHAP: {e}")

if names:
    fig, ax = plt.subplots(figsize=(6,3))
    ax.bar(names, vals)
    ax.set_ylabel("SHAP value")
    ax.tick_params(axis="x", rotation=45)
    st.pyplot(fig)
else:
    st.caption("Không có dữ liệu SHAP để hiển thị.")

st.subheader("Raw context (±5 phút)")
ecs_dir = Path(paths["ecs_parquet_dir"])
parts = list(ecs_dir.rglob("*.parquet"))
try:
    if parts:
        ecs_df = pd.concat([pd.read_parquet(p) for p in parts], ignore_index=True)
        ecs_df["@timestamp"] = pd.to_datetime(ecs_df["@timestamp"], utc=True, errors="coerce")
        t0 = pd.to_datetime(row["@timestamp"], utc=True)
        mask = (ecs_df["@timestamp"] >= t0 - pd.Timedelta(minutes=5)) & (ecs_df["@timestamp"] <= t0 + pd.Timedelta(minutes=5))
        ctx = ecs_df.loc[mask].head(200)
        st.dataframe(ctx, use_container_width=True)
    else:
        st.caption("Không tìm thấy dữ liệu ECS.")
except Exception as e:
    st.warning(f"Không tải được ngữ cảnh: {e}")

st.subheader("Forensic Bundle")
if st.button("Tạo bundle cho alert đang chọn"):
    try:
        bundle_path = build_bundle_for_alert(row, int(idx)+1, thr)
        st.success(f"Bundle created: {bundle_path}")
    except Exception as e:
        st.error(f"Lỗi tạo bundle: {e}")

bundle_candidate = Path(paths["bundles_dir"]) / f"alert_{int(idx)+1}.zip"
if bundle_candidate.exists():
    with open(bundle_candidate, "rb") as f:
        st.download_button("Tải bundle", data=f, file_name=bundle_candidate.name, mime="application/zip")
    st.divider()
    st.subheader("AI Agent Analysis")
    ai_json, ai_md = _load_ai_from_bundle(bundle_candidate)
    if ai_json:
        c1,c2,c3 = st.columns(3)
        c1.metric("Risk", ai_json.get("risk_level","n/a"))
        score = ai_json.get("score")
        c2.metric("Score", f"{score:.3f}" if isinstance(score,(int,float)) else "n/a")
        c3.write(ai_json.get("reason",""))
        iocs = ai_json.get("iocs") or []
        if iocs:
            st.caption("Indicators")
            st.table(iocs)
        actions = ai_json.get("actions") or []
        if actions:
            st.caption("Khuyến nghị")
            for a in actions:
                st.write(f"- {a}")
    if ai_md:
        st.caption("Bản tóm tắt")
        st.markdown(ai_md)
    if not ai_json and not ai_md:
        st.info("Bundle chưa có phân tích AI.")
else:
    st.caption("Chưa có bundle cho alert đang chọn. Nhấn nút để tạo.")