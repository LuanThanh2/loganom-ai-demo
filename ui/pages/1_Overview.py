import sys
from pathlib import Path
from datetime import datetime

# Ensure project root is on sys.path for local imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
from models.utils import get_paths

st.set_page_config(page_title="Loganom AI", layout="wide")

st.title("Loganom AI")

st.markdown(
    """
    Loganom‑AI là hệ thống phát hiện bất thường (tương tự SIEM, không phải IPS) cho log bảo mật.
    Hiện tại dự án sử dụng Isolation Forest (IF) để chấm điểm bất thường, SHAP để giải thích, và SOAR (respond) để mô phỏng hành động ứng phó cục bộ. LSTM (time‑series) đã tích hợp nhưng tạm tắt do giới hạn RAM.
    """
)

with st.expander("Bắt đầu", expanded=True):
    st.code(
        """
        python -m cli.anom_score score
        python -m cli.anom_score respond
        streamlit run ui/streamlit_app.py
        """,
        language="bash",
    )

# Trạng thái dữ liệu gần đây
paths = get_paths()
scores_dir = Path(paths["scores_dir"]) if "scores_dir" in paths else None
logs_dir = Path(paths.get("logs_dir", "data/logs"))
audit_file = logs_dir / "actions.jsonl"

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.subheader("Scores status")
    if scores_dir and scores_dir.exists():
        parquet_files = list(scores_dir.rglob("*.parquet"))
        if parquet_files:
            latest = max(parquet_files, key=lambda p: p.stat().st_mtime)
            ts = datetime.fromtimestamp(latest.stat().st_mtime)
            st.success(f"Tìm thấy {len(parquet_files)} file điểm. Mới nhất: {latest.name} ({ts:%Y-%m-%d %H:%M:%S})")
        else:
            st.warning("Chưa có file .parquet trong thư mục scores.")
    else:
        st.info("Chưa tạo thư mục scores. Hãy chạy: python -m cli.anom_score score")

with col_b:
    st.subheader("SOAR audit")
    if audit_file.exists():
        ts = datetime.fromtimestamp(audit_file.stat().st_mtime)
        size_kb = max(1, audit_file.stat().st_size // 1024)
        st.success(f"actions.jsonl: ~{size_kb} KB, cập nhật: {ts:%Y-%m-%d %H:%M:%S}")
        st.caption("Xem chi tiết tại trang SOAR Actions.")
    else:
        st.info("Chưa có audit. Chạy: python -m cli.anom_score respond hoặc dùng nút trên trang SOAR Actions.")

with col_c:
    st.subheader("LSTM (tùy chọn)")
    st.write("Đã tích hợp LSTM Autoencoder, nhưng với bộ dữ liệu rất lớn cần RAM cao. Tạm thời dùng IF.")

st.divider()
st.info("Nếu muốn chạy nhanh toàn pipeline demo (IF): python -m cli.anom_score demo")