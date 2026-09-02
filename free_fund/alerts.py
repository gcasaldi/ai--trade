from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
import json
import os
from pathlib import Path
import smtplib
import ssl
from typing import Any
from datetime import datetime, timezone

import requests


@dataclass
class AlertManager:
    slack_webhook: str = ""
    enabled: bool = False
    timeout_sec: int = 8
    email_to: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user_env: str = "ALERT_SMTP_USER"
    smtp_password_env: str = "ALERT_SMTP_APP_PASSWORD"
    telegram_token_env: str = "ALERT_TELEGRAM_BOT_TOKEN"
    telegram_chat_id_env: str = "ALERT_TELEGRAM_CHAT_ID"
    state_path: Path | None = None
    min_weight_change: float = 0.02
    reference_capital: float = 100.0
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04

    def _send_email(self, subject: str, body: str) -> bool:
        recipient = self.email_to.strip()
        username = os.getenv(self.smtp_user_env, "").strip()
        password = os.getenv(self.smtp_password_env, "").strip()
        if not self.enabled or not recipient or not username or not password:
            return False

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = username
        message["To"] = recipient
        message.set_content(body)
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=self.timeout_sec) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(username, password)
                smtp.send_message(message)
            return True
        except Exception:
            # Alert failures must never break the analysis loop.
            return False

    def _send_telegram(self, text: str) -> bool:
        token = os.getenv(self.telegram_token_env, "").strip()
        chat_id = os.getenv(self.telegram_chat_id_env, "").strip()
        if not self.enabled or not token or not chat_id:
            return False
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=self.timeout_sec,
            )
            response.raise_for_status()
            return bool(response.json().get("ok", False))
        except Exception:
            return False

    def notify(self, title: str, payload: dict[str, Any]) -> None:
        if not self.enabled:
            return
        serialized = json.dumps(payload, sort_keys=True, indent=2)
        if self.slack_webhook:
            try:
                requests.post(
                    self.slack_webhook,
                    json={"text": f"{title}\n```{serialized}```"},
                    timeout=self.timeout_sec,
                )
            except Exception:
                pass
        text = f"[AI Hedge Fund] {title}\n{serialized}"
        self._send_telegram(text)
        self._send_email(f"[AI Hedge Fund] {title}", serialized)

    def _load_state(self) -> dict[str, Any]:
        if self.state_path is None or not self.state_path.exists():
            return {
                "state_version": 1,
                "target_weights": {},
                "model_positions": {},
                "last_summary_date": "",
            }
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            return {
                "state_version": int(raw.get("state_version", 1)),
                "target_weights": {
                    str(k): float(v) for k, v in raw.get("target_weights", {}).items()
                },
                "model_positions": dict(raw.get("model_positions", {}) or {}),
                "last_summary_date": str(raw.get("last_summary_date", "")),
            }
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return {
                "state_version": 1,
                "target_weights": {},
                "model_positions": {},
                "last_summary_date": "",
            }

    def _save_state(
        self,
        run_id: str,
        weights: dict[str, float],
        positions: dict[str, dict[str, Any]],
        last_summary_date: str,
    ) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(
                {
                    "state_version": 2,
                    "run_id": run_id,
                    "target_weights": weights,
                    "model_positions": positions,
                    "last_summary_date": last_summary_date,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def notify_position_changes(
        self,
        run_id: str,
        target_weights: dict[str, float],
        latest_prices: dict[str, float] | None = None,
    ) -> bool:
        """Email material target changes and persist state only after a successful send."""
        if not self.enabled:
            return False
        state = self._load_state()
        # Version 1 only remembered weights. Rebuild model positions once at
        # current prices, then version 2 distinguishes an intentional exit.
        previous = {} if state["state_version"] < 2 else state["target_weights"]
        positions: dict[str, dict[str, Any]] = state["model_positions"]
        changes: list[str] = []
        exited_symbols: set[str] = set()
        threshold = max(0.0, float(self.min_weight_change))
        prices = latest_prices or {}

        for symbol, position in list(positions.items()):
            if symbol not in prices:
                continue
            price = float(prices[symbol])
            entry = float(position["entry_price"])
            stop = float(position["stop_price"])
            target = float(position["target_price"])
            if price <= stop:
                changes.append(
                    f"AZIONE: VENDI TUTTO {symbol}\n"
                    f"Motivo: il prezzo e sceso al limite di sicurezza.\n"
                    f"Prezzo di ingresso del modello: {entry:.2f}\nPrezzo osservato: {price:.2f}"
                )
                exited_symbols.add(symbol)
                del positions[symbol]
            elif price >= target:
                changes.append(
                    f"AZIONE: VENDI TUTTO {symbol}\n"
                    f"Motivo: il prezzo ha raggiunto l'obiettivo di guadagno.\n"
                    f"Prezzo di ingresso del modello: {entry:.2f}\nPrezzo osservato: {price:.2f}"
                )
                exited_symbols.add(symbol)
                del positions[symbol]

        for symbol in sorted(set(previous) | set(target_weights)):
            old = float(previous.get(symbol, 0.0))
            new = float(target_weights.get(symbol, 0.0))
            if abs(new - old) < threshold:
                continue
            if symbol in exited_symbols and abs(new) < threshold:
                continue
            if abs(old) < threshold and abs(new) >= threshold:
                action = "COMPRA" if new > 0 else "NESSUNA OPERAZIONE"
            elif abs(new) < threshold:
                action = "VENDI TUTTO"
            elif old * new < 0:
                action = "COMPRA" if new > 0 else "VENDI TUTTO"
            elif abs(new) > abs(old):
                action = "COMPRA ANCORA"
            else:
                action = "VENDI UNA PARTE"
            price = float(prices[symbol]) if symbol in prices else None
            amount = max(0.0, new) * max(0.0, float(self.reference_capital))
            line = f"AZIONE: {action} {symbol}\n"
            if action in {"COMPRA", "COMPRA ANCORA"}:
                line += f"Investi in totale circa EUR {amount:.2f}."
            elif action == "VENDI UNA PARTE":
                line += f"Dopo la vendita lascia investiti circa EUR {amount:.2f}."
            else:
                line += "Vendi tutta la posizione indicata dal modello."
            if price is not None:
                line += f"\nPrezzo osservato: {price:.2f}"
                if action in {"COMPRA", "COMPRA ANCORA"} and new > 0:
                    stop = price * (1.0 - max(0.0, float(self.stop_loss_pct)))
                    target = price * (1.0 + max(0.0, float(self.take_profit_pct)))
                    entry_low = price * 0.9975
                    entry_high = price * 1.0025
                    line += (
                        f"\nCompra solo tra {entry_low:.2f} e {entry_high:.2f}."
                        f"\nVendi per limitare la perdita se scende a {stop:.2f}."
                        f"\nValuta di vendere in guadagno se sale a {target:.2f}."
                    )
                    positions[symbol] = {
                        "entry_price": price,
                        "stop_price": stop,
                        "target_price": target,
                        "target_weight": new,
                        "opened_run_id": run_id,
                    }
            if action == "VENDI TUTTO":
                positions.pop(symbol, None)
            changes.append(line)

        today = datetime.now(timezone.utc).date().isoformat()
        if not changes and state["last_summary_date"] != today:
            if positions:
                for symbol, position in sorted(positions.items()):
                    price = float(prices.get(symbol, position["entry_price"]))
                    entry = float(position["entry_price"])
                    pnl = (price / entry - 1.0) if entry > 0 else 0.0
                    changes.append(
                        f"AZIONE: MANTIENI {symbol}\n"
                        f"Prezzo di ingresso del modello: {entry:.2f}\n"
                        f"Prezzo osservato: {price:.2f}\n"
                        f"Guadagno o perdita dal prezzo di ingresso: {pnl:+.1%}\n"
                        f"Vendi per limitare la perdita se scende a {float(position['stop_price']):.2f}.\n"
                        f"Valuta di vendere in guadagno se sale a {float(position['target_price']):.2f}."
                    )
            else:
                changes.append("AZIONE: ATTENDI\nOggi il modello non vede un nuovo acquisto da fare.")

        if not changes:
            return False
        body = (
            "Indicazioni del portafoglio modello\n\n" + "\n\n".join(changes) +
            "\n\nIl bot non esegue ordini. Controlla sempre il prezzo prima di agire. "
            "Niente leva, vendite allo scoperto o criptovalute."
        )
        sent = self._send_telegram(body)
        sent = self._send_email("[AI Hedge Fund] Segnale apri/chiudi posizioni", body) or sent
        if sent:
            self._save_state(
                run_id,
                {k: float(v) for k, v in target_weights.items()},
                positions,
                today,
            )
        return sent
