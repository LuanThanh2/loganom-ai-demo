import sys
import os

def split_log_by_keyword(input_file, keyword):
    output_dir = r"F:\DIFO_GR17\loganom-AI\loganom-ai-demo\sample_data"
    os.makedirs(output_dir, exist_ok=True)
    safe_keyword = keyword.replace(" ", "_")
    output_file = os.path.join(output_dir, f"keyword_{safe_keyword}.log")

    with open(input_file, "r", errors="ignore") as infile, \
         open(output_file, "w") as outfile:
        for line in infile:
            if keyword.lower() in line.lower():
                outfile.write(line)

    print(f"✅ Lọc theo keyword '{keyword}', kết quả ở: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python split_log_by_keyword.py <input_file> <keyword>")
    else:
        split_log_by_keyword(sys.argv[1], sys.argv[2])
