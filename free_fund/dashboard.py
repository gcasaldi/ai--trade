"""Public, allowlisted decision view: no account state or credentials."""
from __future__ import annotations

import json
import math
from pathlib import Path
from datetime import datetime, timezone


def finite(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None


def build_dashboard(decision, prices, cfg, research=None):
    research = research or {}
    flags = list(decision.risk_flags)
    failed = "data_quality_failed" in flags
    generated = datetime.now(timezone.utc)
    price_date = prices.index[-1].date().isoformat() if len(prices) else None
    rows = []
    sectors = cfg.get("portfolio", {}).get("sector_by_symbol", {})
    for symbol in decision.symbols:
        series = prices[symbol].dropna() if symbol in prices else []
        price = finite(series.iloc[-1]) if len(series) else None
        change = finite(series.iloc[-1] / series.iloc[-21] - 1) if len(series) > 20 else None
        volatility = finite(series.pct_change().tail(20).std() * math.sqrt(252)) if len(series) > 20 else None
        weight = finite(decision.target_weights.get(symbol))
        signal = research.get(symbol)
        sentiment = finite(getattr(signal, "sentiment", None))
        urls = [url for url in getattr(signal, "source_urls", []) if isinstance(url, str) and url.startswith("https://")][:3]
        reasons = []
        if failed:
            reasons.append("Controllo qualità non superato: nessuna nuova indicazione utilizzabile.")
        elif weight is not None and weight > 0:
            reasons.append(f"Il modello assegna a questo titolo il {weight:.1%} del capitale, dopo i limiti di rischio.")
        else:
            reasons.append("Il modello non assegna capitale a questo titolo in questa analisi.")
        if change is not None:
            reasons.append(f"Variazione nelle ultime 20 sedute disponibili: {change:+.1%}.")
        if volatility is not None:
            reasons.append(f"Volatilità annualizzata sulle ultime 20 variazioni giornaliere: {volatility:.1%}.")
        if not urls:
            reasons.append("Nessuna fonte di notizie recente disponibile per questa analisi.")
        rows.append({
            "symbol": symbol, "sector": sectors.get(symbol, ""),
            "target_weight": weight, "reference_price_usd": price,
            "return_20d": change, "volatility_20d": volatility,
            "news_sentiment": sentiment, "source_urls": urls, "reasons": reasons,
        })
    alerts = cfg.get("alerts", {})
    return {
        "schema_version": 1, "status": "unavailable" if failed else "ready",
        "generated_at": generated.isoformat(), "decision_at": decision.timestamp_utc,
        "price_date": price_date, "price_source": "Yahoo Finance · chiusure giornaliere rettificate",
        "max_price_age_hours": float(cfg.get("data_quality", {}).get("max_staleness_minutes", 2880)) / 60,
        "model": "AI Native Hedge Fund · strategia e controllo del rischio",
        "ai_trader_integrated": False, "risk_flags": flags,
        "rules": {
            "stop_loss_pct": float(alerts.get("stop_loss_pct", .02)),
            "take_profit_pct": float(alerts.get("take_profit_pct", .04)),
            "minimum_position_eur": float(alerts.get("minimum_position_amount", 20)),
            "min_weight_change": float(alerts.get("min_weight_change", .02)),
            "commission_per_order_eur": float(alerts.get("commission_per_order", 1)),
            "minimum_net_profit_pct": float(alerts.get("minimum_net_profit_pct", .02)),
            "estimated_tax_rate": float(alerts.get("estimated_tax_rate", .26)),
        },
        "assets": rows,
    }


def write_dashboard(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    temporary.replace(path)
