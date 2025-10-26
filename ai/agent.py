"""
AI agent phân tích alert bằng LLM (tiếng Việt).
Ưu tiên: DeepSeek -> Gemini -> Offline stub.
"""

from __future__ import annotations
import os, re, logging
from typing import Dict, Any, List, Optional

# --------- Chuẩn hóa đầu vào ---------
def _as_records(obj: Any) -> List[Dict[str, Any]]:
    try:
        import pandas as pd  # type: ignore
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict("records")
    except Exception:
        pass
    if isinstance(obj, (list, tuple)):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for k in ("records", "rows", "data", "items"):
            v = obj.get(k)
            if isinstance(v, (list, tuple)):
                return [x for x in v if isinstance(x, dict)]
        vals = list(obj.values())
        if vals and isinstance(vals[0], dict):
            return [x for x in vals if isinstance(x, dict)]
    return []

def _as_list(obj: Any) -> List[Any]:
    if obj is None:
        return []
    if isinstance(obj, (list, tuple)):
        return list(obj)
    if isinstance(obj, dict):
        for k in ("items", "rows", "data", "values"):
            v = obj.get(k)
            if isinstance(v, (list, tuple)):
                return list(v)
        return list(obj.values())
    return [obj]

# --------- Tạo prompt ---------
def _truncate(s: str, n: int) -> str:
    if s is None: return ""
    s = str(s)
    return s if len(s) <= n else s[: n - 3] + "..."

def _render_prompt(
    alert: Dict[str, Any],
    shap_items: List[Dict[str, Any]],
    context_rows: List[Dict[str, Any]],
    max_ctx_lines: int = 20,
    max_ctx_chars: int = 200,
) -> str:
    shap_list = _as_list(shap_items)
    ctx_list = _as_records(context_rows)

    parts: List[str] = []
    parts.append("Bạn là chuyên gia SOC. Hãy phân tích NGẮN GỌN, RÕ RÀNG, BẰNG TIẾNG VIỆT.")
    parts.append(f"Thời điểm cảnh báo: {alert.get('@timestamp')}, điểm bất thường: {alert.get('anom.score')}")
    parts.append(
        "Thực thể: "
        f"host={alert.get('host.name')}, user={alert.get('user.name')}, "
        f"src={alert.get('source.ip')}, dst={alert.get('destination.ip')}"
    )

    if shap_list:
        items = ", ".join(
            f"{x.get('feature')}({float(x.get('value', 0.0)):+.3f})"
            for x in shap_list[:5] if isinstance(x, dict)
        )
        if items:
            parts.append(f"Đặc trưng nổi bật: {items}")

    if ctx_list:
        msgs = []
        for r in ctx_list[:max_ctx_lines]:
            if not isinstance(r, dict): continue
            msg = r.get("message") or ""
            ts = r.get("@timestamp") or ""
            mod = r.get("event.module") or ""
            ds = r.get("event.dataset") or ""
            msgs.append(f"[{ts}][{mod}.{ds}] {_truncate(str(msg), max_ctx_chars)}")
        if msgs:
            parts.append("Ngữ cảnh (rút gọn):\n- " + "\n- ".join(msgs))

    parts.append(
        "Đầu ra yêu cầu: 1) Mức rủi ro (LOW/MEDIUM/HIGH); "
        "2) Lý do ngắn gọn; 3) Ba hành động khuyến nghị cụ thể (có thể kèm script PowerShell). "
        "Chỉ trả lời bằng tiếng Việt."
    )
    return "\n".join(parts)

# --------- Suy diễn mức rủi ro ---------
_RISK_PATTERNS = [
    (r"\b(thấp|low)\b", "LOW"),
    (r"\b(trung\s*bình|vừa|medium|med|moderate)\b", "MEDIUM"),
    (r"\b(cao|nghiêm\s*trọng|critical|high)\b", "HIGH"),
]

def _infer_risk_from_text(text: str, default: str = "LOW") -> str:
    if not text: return default
    t = text.lower()
    for pat, level in _RISK_PATTERNS:
        if re.search(pat, t, flags=re.IGNORECASE):
            return level
    return default

# --------- Gợi ý hành động có script (Windows) ---------
def _dedup_keep_order(items: List[str]) -> List[str]:
    seen, out = set(), []
    for it in items:
        if it not in seen:
            out.append(it); seen.add(it)
    return out

def _suggest_actions(alert: Dict[str, Any]) -> List[str]:
    """
    Sinh danh sách bước khuyến nghị ngắn gọn, có kèm script PowerShell khi phù hợp.
    Lưu ý: nhiều lệnh cần quyền Admin; kiểm tra trước khi áp dụng trong môi trường thật.
    """
    actions: List[str] = []

    ip = (alert.get("source.ip") or "").strip()
    user = (alert.get("user.name") or "").strip()
    host = (alert.get("host.name") or "").strip()
    proc = (alert.get("process.name") or alert.get("process.executable") or "").strip()

    # 1) Chặn IP nguồn (nếu có)
    if ip:
        actions.append(f"Chặn IP nguồn tạm thời (PowerShell/Administrator): New-NetFirewallRule -DisplayName \"Block inbound {ip}\" -Direction Inbound -RemoteAddress {ip} -Action Block; New-NetFirewallRule -DisplayName \"Block outbound {ip}\" -Direction Outbound -RemoteAddress {ip} -Action Block")

    # 2) Bảo vệ tài khoản người dùng (nếu có)
    if user:
        actions.append(f"Tạm khóa tài khoản cục bộ: net user {user} /active:no  (Domain: Disable-ADAccount -Identity {user})")
        actions.append(f"Buộc đổi mật khẩu: Set-ADAccountPassword -Identity {user} -Reset -NewPassword (Read-Host -AsSecureString)  (nếu là tài khoản AD)")

    # 3) Cách ly endpoint (nếu biết host) – giữ RDP để điều tra
    if host:
        actions.append("Cách ly endpoint bằng Firewall (chạy tại máy hoặc qua RMM): Set-NetFirewallProfile -Profile Domain,Public,Private -DefaultInboundAction Block -DefaultOutboundAction Block; New-NetFirewallRule -DisplayName \"Allow RDP\" -Direction Inbound -Protocol TCP -LocalPort 3389 -Action Allow")

    # 4) Quét AV và thu thập log chứng cứ
    actions.append("Kích hoạt quét Defender: Start-MpScan -ScanType QuickScan  (FullScan nếu cần)")
    actions.append("Thu thập log sự kiện: wevtutil epl Security C:\\Temp\\Security.evtx /ow:true; wevtutil epl System C:\\Temp\\System.evtx /ow:true")

    # 5) Xử lý tiến trình nghi ngờ (nếu có tên/đường dẫn)
    if proc:
        actions.append(f"Dừng tiến trình nghi ngờ: Stop-Process -Name \"{proc}\" -Force  (xem xét trước với tiến trình hệ thống)")
        actions.append("Lấy hash file để tra cứu IOC: Get-FileHash -Algorithm SHA256 \"<path_to_exe>\"")

    # 6) Khôi phục/khoanh vùng quyền truy cập
    if user:
        actions.append("Rút quyền admin tạm thời khỏi user nghi vấn (Local Administrators/Groups).")

    # 7) Theo dõi và đóng sự cố
    actions.append("Theo dõi log ±5 phút quanh thời điểm và các đăng nhập/tiến trình bất thường liên quan; đóng rule chặn khi đã xác minh an toàn.")

    return _dedup_keep_order([a for a in actions if a])

# --------- Gọi LLM ---------
def _call_deepseek(prompt: str) -> Optional[str]:
    ds_key = os.getenv("DEEPSEEK_API_KEY")
    if not ds_key: return None
    try:
        from openai import OpenAI  # pip install openai
        base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com")
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        client = OpenAI(api_key=ds_key, base_url=base)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Bạn là chuyên gia SOC. Luôn trả lời bằng tiếng Việt, ngắn gọn và hành động được."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=700,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        logging.exception("DeepSeek call failed: %s", e)
        return None

def _call_gemini(prompt: str) -> Optional[str]:
    gkey = os.getenv("GEMINI_API_KEY")
    if not gkey: return None
    try:
        import google.generativeai as genai  # pip install google-generativeai
        genai.configure(api_key=gkey)
        model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
        res = model.generate_content("Trả lời bằng tiếng Việt, ngắn gọn, hành động được.\n\n" + prompt)
        return (getattr(res, "text", None) or "").strip()
    except Exception as e:
        logging.exception("Gemini call failed: %s", e)
        return None

# --------- API chính ---------
def analyze_alert_with_llm(
    alert: Dict[str, Any],
    shap_items: List[Dict[str, Any]],
    context_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    prompt = _render_prompt(alert, shap_items, context_rows)

    text = _call_deepseek(prompt)
    provider = "deepseek"

    if text is None:
        text = _call_gemini(prompt)
        provider = "gemini" if text is not None else "stub"

    actions = _suggest_actions(alert)

    if not text:
        return {
            "risk_level": "LOW",
            "score": float(alert.get("anom.score") or 0.0),
            "reason": "Chế độ offline: chưa cấu hình LLM, không thể sinh phân tích tự động.",
            "iocs": [
                {"type": "host.name", "value": alert.get("host.name")},
                {"type": "user.name", "value": alert.get("user.name")},
                {"type": "source.ip", "value": alert.get("source.ip")},
                {"type": "destination.ip", "value": alert.get("destination.ip")},
            ],
            "actions": actions,
            "raw_text": "",
            "provider": provider,
            "alert_time": str(alert.get("@timestamp")),
        }

    risk = _infer_risk_from_text(text, default="LOW")
    return {
        "risk_level": risk,
        "score": float(alert.get("anom.score") or 0.0),
        "reason": _truncate(text, 1200),
        "iocs": [
            {"type": "host.name", "value": alert.get("host.name")},
            {"type": "user.name", "value": alert.get("user.name")},
            {"type": "source.ip", "value": alert.get("source.ip")},
            {"type": "destination.ip", "value": alert.get("destination.ip")},
        ],
        "actions": actions,  # kèm script/phòng chống
        "raw_text": text,
        "provider": provider,
        "alert_time": str(alert.get("@timestamp")),
    }

# Alias tương thích
def analyze_alert(alert: Dict[str, Any], shap_items: List[Dict[str, Any]], context_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    return analyze_alert_with_llm(alert, shap_items, context_rows)