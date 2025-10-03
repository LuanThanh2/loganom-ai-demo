loganom-ai-demo

An offline, end-to-end demo that ingests synthetic cyber security logs, normalizes them to ECS, engineers time-window/session/entropy features, trains an Isolation Forest, explains top anomalies with SHAP, and packages forensics-ready bundles. Includes a Typer CLI and a Streamlit UI.

Hướng dẫn sử dụng dự án
1. Chuẩn bị
Python (phiên bản giống venv bạn đang dùng, ví dụ 3.12).
Tại thư mục gốc repo:
2. Dữ liệu đầu vào
Thư mục: sample_data/
*.log (syslog/auth) → parser log_parser.py tự quét đệ quy.
*.csv (flow / CICIDS / ISCX) → parser csv_parser.py tự quét đệ quy.
(Nếu có JSONL mặc định của demo cũ thì run_ingest sẽ xử lý; thiếu file không sao).
Có thể giới hạn nguồn bằng biến:
3. Chạy pipeline đầy đủ
Tùy chọn:

Reset sạch trước khi chạy:
Giữ model cũ:
Tắt tạo bundle:
4. Chạy từng bước
5. Reset chọn lọc
Tự động reset mỗi lần demo:

6. Dashboard UI
Trang Alerts (ui/pages/3_Alerts.py): xem alert, SHAP, tạo bundle, tải zip.
Nếu dữ liệu cũ: chạy lại pipeline + restart Streamlit.
7. Thêm / sửa log đầu vào
Thêm file .log mới vào sample_data (định dạng syslog chuẩn).
Thêm CSV: chỉ cần có cột thời gian (Timestamp / Start Time / DateTime...). Nếu tên khác, đặt:
Chạy lại ingest (và các bước sau):
8. Kiểm tra nhanh kết quả
9. Troubleshooting nhanh
Vấn đề	Cách xử lý
No module named 'cli'	Đảm bảo đang ở thư mục gốc repo; có __init__.py
Không thấy dữ liệu mới	Reset phần liên quan + chạy lại ingest→featurize→score
Không tạo bundle	Chưa có scores.parquet hoặc không có alert vượt ngưỡng
CSV bị skip (Thiếu cột thời gian)	Đổi tên cột hoặc CSV_TIME_COL
SHAP lỗi	Model chưa train lại hoặc feature_cols không khớp
10. Quy trình lặp khi đổi dữ liệu
Cập nhật file trong sample_data/
python -m cli.anom_score ingest --reset
python -m cli.anom_score featurize --reset
(Tùy) python -m cli.anom_score train (nếu muốn retrain)
python -m cli.anom_score score --reset
python -m cli.anom_score bundle
Reload Streamlit.
Quickstart

1) Create a virtual environment

```
py -3.12 -m venv venv312
.\venv312\Scripts\Activate.ps1
```

2) Install dependencies

```
pip install -r requirements.txt
```

3) Run the full demo pipeline

```
python -m cli.anom_score demo
```

4) Launch the dashboard

```
streamlit run ui/streamlit_app.py
```

Repository Layout

```
loganom-ai-demo/
  README.md
  requirements.txt
  config/
  sample_data/
  parsers/
  features/
  models/
  explain/
  pipeline/
  ui/
  cli/
  bundles/  # artifacts (gitignored)
  data/     # parquet, features, models (gitignored)
```

What the demo does

- Ingest synthetic Windows, Sysmon, Zeek, and syslog auth logs
- Normalize to ECS using configurable mappings
- Write partitioned Parquet stores per source under `data/ecs_parquet/{source}/dt=YYYY-MM-DD/`
- Build features: sliding window counts/rates (1/5/15m), entropy for strings, and simple sessionization
- Train an Isolation Forest (configurable via `config/models.yaml`)
- Score anomalies, explain top-N via SHAP, and create forensic bundles containing:
  - raw_logs.jsonl (±5 minutes of ECS events)
  - features.json (the event vector)
  - shap_explanation.json (top-5 SHAP contributors)
  - model_meta.json (model version, threshold)
  - manifest.json (file SHA256 hashes)

Forensic Bundle

Each bundle is a .zip in `bundles/` with files listed above. Use the Streamlit UI Alerts page to download a bundle for an alert, or generate via CLI `bundle`.

Notes

- CPU only; small datasets run in <2 minutes on a laptop.
- Offline-first: all sample data is included; no network required at runtime.


### Hướng dẫn nhanh (Tiếng Việt)

1) Tạo môi trường ảo và kích hoạt (PowerShell):

```
python -m venv venv
.\\venv\\Scripts\\Activate.ps1
```

2) Cài đặt thư viện:

```
pip install -r requirements.txt
```

3) Chạy toàn bộ pipeline demo (hãy đứng trong thư mục `loganom-ai-demo`):

```
python -m cli.anom_score demo
```

4) Mở giao diện Streamlit:

```
streamlit run ui\\streamlit_app.py
```

Ghi chú vận hành

- Nên `cd` vào thư mục `loganom-ai-demo` trước khi chạy các lệnh Python dạng module.
- Dữ liệu tạo sẵn ở `sample_data/`. Kết quả ingest sẽ nằm ở `data/ecs_parquet/`.
- Bảng đặc trưng tại `data/features/features.parquet`, model ở `data/models/`, điểm số ở `data/scores/`.
- Forensic Bundles (.zip) được lưu trong `bundles/` và có thể tải từ trang Alerts của UI.

🔹 Cách dùng

Lọc theo ngày:

python log_by_date.py Windows.log 2016-09-28


Lọc theo keyword:
(vd: ERROR, Failed, Unauthorized)

python log_by_keyword.py Windows.log ERROR


Lọc theo khoảng ngày:

python log_by_range.py Windows.log 2016-09-28 2016-10-02
