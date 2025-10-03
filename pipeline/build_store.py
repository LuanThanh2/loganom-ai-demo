from pathlib import Path

from models.utils import get_paths
from parsers.evtx_parser import parse_evtx
from parsers.sysmon_parser import parse_sysmon
from parsers.zeek_parser import parse_zeek_conn
from parsers.syslog_parser import parse_auth_log


def run_ingest() -> Path:
    # Run all parsers
    parse_evtx()
    parse_sysmon()
    parse_zeek_conn()
    parse_auth_log()
    return Path(get_paths()["ecs_parquet_dir"])  


if __name__ == "__main__":
    run_ingest()
