from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from dateutil import tz

from models.utils import get_paths

SYSLOG_RE = re.compile(
    r"^(?P<mon>\w{3})\s+(?P<day>\d{1,2})\s(?P<time>\d{2}:\d{2}:\d{2})\s(?P<host>[^\s]+)\s(?P<proc>[^:]+):\s(?P<msg>.*)$"
)
IP_RE = re.compile(r"\b(?P<ip>(?:\d{1,3}\.){3}\d{1,3})\b")
USER_FAIL_RE = re.compile(r"Failed password for (?:invalid user\s+)?(?P<user>[\w\-\.\$]+)")
USER_OK_RE = re.compile(r"Accepted (?:password|publickey) for (?P<user>[\w\-\.\$]+)")
MONTH_MAP = {m: i for i, m in enumerate(["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], start=1)}

def _parse_ts(mon: str, day: str, hhmmss: str) -> Optional[pd.Timestamp]:
    try:
        year = datetime.utcnow().year
        dt_naive = datetime(year=year, month=MONTH_MAP[mon.title()], day=int(day))
        t = datetime.strptime(hhmmss, "%H:%M:%S").time()
        dt_local = datetime.combine(dt_naive, t)
        tzname = os.getenv("TZ", "UTC")
        local = tz.gettz(tzname) or tz.UTC
        dt_local = dt_local.replace(tzinfo=local)
        return pd.Timestamp(dt_local).tz_convert("UTC")
    except Exception:
        return None

def _rows_from_logfile(p: Path) -> List[Dict]:
    rows: List[Dict] = []
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.rstrip("\n")
            m = SYSLOG_RE.match(line)
            if not m:
                continue
            gd = m.groupdict()
            ts = _parse_ts(gd["mon"], gd["day"], gd["time"])
            host = gd.get("host")
            proc = gd.get("proc")
            msg = gd.get("msg", "")

            action = "user_login"
            outcome = None
            user = None
            if "Failed password" in msg or "authentication failure" in msg:
                outcome = "Failure"
                uf = USER_FAIL_RE.search(msg)
                if uf:
                    user = uf.group("user")
            elif "Accepted " in msg:
                outcome = "Success"
                uo = USER_OK_RE.search(msg)
                if uo:
                    user = uo.group("user")

            ip = None
            ipm = IP_RE.search(msg)
            if ipm:
                ip = ipm.group("ip")

            rows.append({
                "@timestamp": ts.isoformat() if ts is not None else None,
                "host.name": host,
                "process.name": proc,
                "message": msg,
                "event.module": "syslog",
                "event.dataset": "auth",
                "event.action": action,
                "event.outcome": outcome,
                "user.name": user,
                "source.ip": ip,
                "log.file.path": str(p),
            })
    return rows

def parse_auth_logs(root: Path = Path("sample_data")) -> Path:
    paths = get_paths()
    out_root = Path(paths["ecs_parquet_dir"]).resolve()
    out_dir_root = out_root / "syslog_auth"
    out_dir_root.mkdir(parents=True, exist_ok=True)
    log_files = list(root.rglob("*.log"))
    if not log_files:
        return out_root
    all_rows: List[Dict] = []
    for p in log_files:
        try:
            all_rows.extend(_rows_from_logfile(p))
        except Exception:
            continue
    if not all_rows:
        return out_root
    df = pd.DataFrame(all_rows)
    df = df.dropna(subset=["@timestamp"])
    df["@timestamp"] = pd.to_datetime(df["@timestamp"], utc=True, errors="coerce")
    df = df.dropna(subset=["@timestamp"])
    df["dt"] = df["@timestamp"].dt.strftime("%Y-%m-%d")
    keep_cols = [
        "@timestamp","event.module","event.dataset","event.action","event.outcome",
        "host.name","user.name","process.name","source.ip","message","log.file.path"
    ]
    for d, g in df.groupby("dt", dropna=True):
        out_dir = out_dir_root / f"dt={d}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "part.parquet").unlink(missing_ok=True)
        g[keep_cols].to_parquet(out_dir / "part.parquet", index=False)
    return out_root

def parse_auth_log() -> Path:
    return parse_auth_logs(Path("sample_data"))