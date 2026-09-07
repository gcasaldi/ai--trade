"""Read-only AI-Trader sample audit. Never sends signals or executes trades."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen


def audit(payload, symbols, now, max_age_hours=24):
    rows = payload.get("signals")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("Expected a signals array of objects")
    results = []
    for row in rows:
        reasons = []
        symbol = str(row.get("symbol") or "").upper()
        if symbol not in symbols:
            reasons.append("outside_universe")
        if row.get("message_type") != "operation" or row.get("market") != "us-stock":
            reasons.append("wrong_signal_type_or_market")
        if row.get("side") not in {"buy", "sell"}:
            reasons.append("unsupported_action")
        for field in ("entry_price", "quantity"):
            value = row.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                reasons.append("invalid_" + field)
        try:
            timestamp = datetime.fromisoformat(row["executed_at"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                raise ValueError("Timestamp needs timezone")
            age = (now - timestamp).total_seconds() / 3600
            if age < 0 or age > max_age_hours:
                reasons.append("future_or_older_than_age_limit")
        except (KeyError, ValueError, TypeError, AttributeError):
            reasons.append("invalid_execution_time")
        if "[Copied from " in str(row.get("content") or ""):
            reasons.append("declared_copy")
        # An executed operation is not a fresh, portfolio-sized trading plan.
        results.append({
            "signal_id": row.get("signal_id"), "agent_id": row.get("agent_id"),
            "symbol": symbol, "action": row.get("side"),
            "reported_price": row.get("entry_price"), "provider_quantity": row.get("quantity"),
            "executed_at": row.get("executed_at"), "reasons": reasons,
            "eligible_for_research": not reasons, "executable": False,
        })
    return {
        "as_of": now.isoformat(), "universe": sorted(symbols),
        "max_age_hours": max_age_hours, "sample_size": len(rows),
        "platform_total": payload.get("total"),
        "eligible_for_research": sum(r["eligible_for_research"] for r in results),
        "reason_counts": dict(Counter(reason for r in results for reason in r["reasons"])),
        "limitations": [
            "Sample only, not an exhaustive search or performance comparison.",
            "Age limit uses elapsed hours, not exchange sessions.",
            "Provider quantities are not sized to our capital or holdings.",
            "No current quote, entry validity, exit rule, fills or net returns verified.",
            "No operation is an executable recommendation from this audit.",
        ],
        "operations": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, help="Replay a previously saved JSON snapshot")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--symbols", nargs="+", required=True, help="Explicit comparison universe from the chosen runtime config")
    parser.add_argument("--as-of", help="Timezone-aware ISO timestamp for reproducible replay")
    parser.add_argument("--max-age-hours", type=float, default=24)
    args = parser.parse_args()
    if not math.isfinite(args.max_age_hours) or args.max_age_hours <= 0:
        parser.error("--max-age-hours must be positive and finite")
    now = datetime.fromisoformat(args.as_of.replace("Z", "+00:00")) if args.as_of else datetime.now(timezone.utc)
    if now.tzinfo is None:
        parser.error("--as-of requires a timezone")
    url = "https://ai4trade.ai/api/signals/feed?" + urlencode({
        "message_type": "operation", "market": "us-stock", "limit": 100, "sort": "new",
    })
    if args.snapshot:
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8-sig"))
    else:
        with urlopen(url, timeout=30) as response:
            snapshot = {"source_url": url, "fetched_at": now.isoformat(), "payload": json.load(response)}
    report = audit(snapshot["payload"], {s.upper() for s in args.symbols}, now, args.max_age_hours)
    report["source_url"] = snapshot.get("source_url")
    report["fetched_at"] = snapshot.get("fetched_at")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    (args.output / "audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "operations"}, indent=2))


if __name__ == "__main__":
    main()
