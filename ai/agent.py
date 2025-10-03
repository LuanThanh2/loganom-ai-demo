import os
from datetime import datetime
from typing import Dict, Any, List

def _fallback_analysis(alert_row, shap_top: Dict[str, Any], raw_context) -> Dict[str, Any]:
    score = float(alert_row.get("anom.score", 0.0))
    risk = "HIGH" if score >= 0.95 else "MEDIUM" if score >= 0.85 else "LOW"
    iocs = []
    for col in ["source.ip", "destination.ip", "host.name", "user.name", "process.name"]:
        v = alert_row.get(col)
        if isinstance(v, str) and v:
            iocs.append({"type": col, "value": v})
    top_feats = shap_top.get("top_features", []) if shap_top else []
    reason = ", ".join(f"{f['feature']}({f['value']:+.3f})" for f in top_feats[:5])
    md = (
        f"# AI Alert Analysis\n\n"
        f"- Time: {alert_row.get('@timestamp')}\n"
        f"- Score: {score:.4f}\n"
        f"- Risk: {risk}\n"
        f"- Key contributors: {reason or 'n/a'}\n\n"
        f"## Observations\n"
        f"- Host: {alert_row.get('host.name')}, User: {alert_row.get('user.name')}\n"
        f"- SrcIP: {alert_row.get('source.ip')}, DstIP: {alert_row.get('destination.ip')}\n\n"
        f"## Recommended actions\n"
        f"- Triage related events ±5m.\n"
        f"- Validate user/session and process lineage.\n"
        f"- Contain host if malicious indicators confirmed.\n"
    )
    return {
        "created_at": datetime.utcnow().isoformat() + "Z",
        "risk_level": risk,
        "score": score,
        "reason": reason,
        "iocs": iocs,
        "actions": [
            "Review correlated events in the provided context.",
            "Verify account activity and process tree.",
            "Isolate endpoint if needed; rotate credentials."
        ],
        "markdown": md,
    }

def analyze_alert(alert_row, shap_top: Dict[str, Any], raw_context) -> Dict[str, Any]:
    """
    Returns a dict with fields: created_at, risk_level, score, reason, iocs[], actions[], markdown.
    Tries Gemini if available via GEMINI_API_KEY, otherwise falls back to offline heuristic.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _fallback_analysis(alert_row, shap_top, raw_context)

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)

        # Build compact prompt
        score = float(alert_row.get("anom.score", 0.0))
        top_feats = shap_top.get("top_features", []) if shap_top else []
        ctx_rows = raw_context.head(50).to_dict(orient="records") if hasattr(raw_context, "head") else []

        prompt = f"""
You are a SOC analyst. Summarize this anomaly and produce JSON with keys
[risk_level (LOW/MEDIUM/HIGH), reason, iocs (list of {{type,value}}), actions (list of strings)],
then provide a short markdown narrative.

Score: {score}
TopFeatures: {top_feats}
AlertRow: {dict(alert_row)}
ContextSample: {ctx_rows[:10]}
Return JSON first, then a markdown section delimited by <<<MD ... MD>>>.
"""

        model = genai.GenerativeModel("gemini-1.5-flash")
        resp = model.generate_content(prompt)
        text = resp.text or ""
        # Very light parsing: find JSON block
        import json, re
        m = re.search(r"\{.*\}", text, re.S)
        data = _fallback_analysis(alert_row, shap_top, raw_context)
        if m:
            try:
                parsed = json.loads(m.group(0))
                data.update({
                    "risk_level": parsed.get("risk_level", data["risk_level"]),
                    "reason": parsed.get("reason", data["reason"]),
                    "iocs": parsed.get("iocs", data["iocs"]),
                    "actions": parsed.get("actions", data["actions"]),
                })
            except Exception:
                pass
        m2 = re.search(r"<<<MD(.*?)MD>>>", text, re.S)
        if m2:
            data["markdown"] = m2.group(1).strip()
        return data
    except Exception:
        return _fallback_analysis(alert_row, shap_top, raw_context)