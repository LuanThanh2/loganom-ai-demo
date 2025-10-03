import sys
import os
from datetime import datetime

def split_log_by_range(input_file, start_date, end_date):
    output_dir = r"F:\DIFO_GR17\loganom-AI\loganom-ai-demo\sample_data"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"range_{start_date}_to_{end_date}.log")

    # chuyển string sang datetime
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    with open(input_file, "r", errors="ignore") as infile, \
         open(output_file, "w") as outfile:
        for line in infile:
            try:
                date_str = line.split()[0]  # lấy yyyy-mm-dd
                current = datetime.strptime(date_str, "%Y-%m-%d")
                if start <= current <= end:
                    outfile.write(line)
            except Exception:
                continue  # bỏ qua dòng không hợp lệ

    print(f"✅ Lọc theo khoảng ngày {start_date} → {end_date}, kết quả ở: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python split_log_by_range.py <input_file> <start_date> <end_date>")
    else:
        split_log_by_range(sys.argv[1], sys.argv[2], sys.argv[3])
