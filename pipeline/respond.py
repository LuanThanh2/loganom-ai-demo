"""Local SOAR responder (Windows-friendly, offline).

Evaluates alerts and executes response actions based on config/policy.yaml.
Default is dry-run (plan only). Requires admin for apply.
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import yaml

from models.utils import get_paths, ensure_dir


def _load_policy() -> Dict[str, Any]:
    paths = get_paths()
    p = Path(paths["raw_data_dir"]).parents[0] / "config" / "policy.yaml"
    if not p.exists():
        # default minimal policy
        return {
            "rules": [
                {
                    "name": "Pause Windows Update on high anomaly",
                    "condition": {"score_col": "ensemble.score", "gte": 0.95},
                    "actions": [
                        {"type": "powershell", "cmd": "net stop wuauserv"},
                        {"type": "powershell", "cmd": "dism /online /cleanup-image /scanhealth"},
                        {"type": "powershell", "cmd": "sfc /scannow"}
                    ],
                }
            ]
        }
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _match(row: pd.Series, cond: Dict[str, Any]) -> bool:
    col = cond.get("score_col", "anom.score")
    gte = cond.get("gte")
    lte = cond.get("lte")
    val = float(row.get(col, 0.0))
    if gte is not None and val < float(gte):
        return False
    if lte is not None and val > float(lte):
        return False
    return True


def _exec_action(action: Dict[str, str], dry_run: bool) -> Tuple[str, int]:
    t = action.get("type")
    cmd = action.get("cmd", "")
    if dry_run:
        return f"DRY-RUN {t}: {cmd}", 0
    try:
        # Use shell=True for PowerShell/cmd commands on Windows
        proc = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        rc = proc.returncode
        out = (proc.stdout or "") + (proc.stderr or "")
        return out.strip(), rc
    except Exception as e:
        return f"ERROR: {e}", 1


def respond(alerts_path: Path = None, dry_run: bool = True) -> Path:
    paths = get_paths()
    scores_root = Path(paths["scores_dir"]).resolve()
    if alerts_path is None:
        # prefer ensemble; fallback to scores.parquet
        candidate = scores_root / "ensemble_scores.parquet"
        alerts_path = candidate if candidate.exists() else (scores_root / "scores.parquet")

    df = pd.read_parquet(alerts_path)
    if df.empty:
        raise RuntimeError("No alerts/scores to evaluate")

    policy = _load_policy()
    rules = policy.get("rules", [])

    logs_dir = Path(paths["logs_dir"]).resolve()
    ensure_dir(logs_dir)
    audit = logs_dir / "actions.jsonl"

    now = datetime.utcnow().isoformat() + "Z"
    with open(audit, "a", encoding="utf-8") as f:
        for _, row in df.iterrows():
            for rule in rules:
                if _match(row, rule.get("condition", {})):
                    for act in rule.get("actions", []):
                        output, rc = _exec_action(act, dry_run=dry_run)
                        # Ensure JSON-serializable fields
                        row_ts_val = row.get("@timestamp")
                        try:
                            row_ts_str = (
                                pd.to_datetime(row_ts_val, utc=True).isoformat()
                                if pd.notna(row_ts_val)
                                else None
                            )
                        except Exception:
                            row_ts_str = str(row_ts_val) if row_ts_val is not None else None

                        rec = {
                            "time": now,
                            "dry_run": bool(dry_run),
                            "rule": str(rule.get("name")),
                            "row_ts": row_ts_str,
                            "score": float(
                                row.get(
                                    rule.get("condition", {}).get("score_col", "anom.score"),
                                    0.0,
                                )
                            ),
                            "action": {
                                "type": str(act.get("type")),
                                "cmd": str(act.get("cmd", "")),
                            },
                            "return_code": int(rc),
                            "output": str(output),
                        }
                        f.write(json.dumps(rec) + "\n")

    return audit


if __name__ == "__main__":
    respond(dry_run=True)


