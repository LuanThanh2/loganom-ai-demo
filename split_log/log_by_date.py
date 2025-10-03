import sys
import os

def split_log_by_date(input_file, date_str):
    output_dir = r"F:\DIFO_GR17\loganom-AI\loganom-ai-demo\sample_data"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{date_str}.log")

    with open(input_file, "r", errors="ignore") as infile, \
         open(output_file, "w") as outfile:
        for line in infile:
            if line.startswith(date_str):
                outfile.write(line)

    print(f"✅ Lọc theo ngày {date_str}, kết quả ở: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python split_log_by_date.py <input_file> <date>")
    else:
        split_log_by_date(sys.argv[1], sys.argv[2])
