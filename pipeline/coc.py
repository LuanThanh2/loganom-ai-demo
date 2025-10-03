import os
import platform
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from models.utils import sha256_file  # uses existing helper

def build_coc(output_dir: Path, input_files: List[Path], extra_outputs: List[Path]) -> Dict:
    created_at = datetime.utcnow().isoformat() + "Z"
    def _rec(paths: List[Path]):
        out = []
        for p in paths:
            p = Path(p)
            if p.exists():
                out.append({
                    "path": str(p.resolve()),
                    "sha256": sha256_file(p),
                    "size": p.stat().st_size,
                })
        return out

    return {
        "created_at": created_at,
        "operator": os.getenv("OPERATOR_ID", "unknown"),
        "env": {
            "hostname": platform.node(),
            "platform": platform.platform(),
            "app_env": os.getenv("APP_ENV", "development"),
            "tz": os.getenv("TZ", "UTC"),
        },
        "inputs": _rec(input_files),
        "outputs": _rec(extra_outputs),
    }