from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
import json
import os
from pathlib import Path
import smtplib
import ssl
from typing import Any

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

    def _load_weights(self) -> dict[str, float]:
        if self.state_path is None or not self.state_path.exists():
            return {}
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            return {str(k): float(v) for k, v in raw.get("target_weights", {}).items()}
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return {}

    def _save_weights(self, run_id: str, weights: dict[str, float]) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps({"run_id": run_id, "target_weights": weights}, indent=2, sort_keys=True),
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
        previous = self._load_weights()
        changes: list[str] = []
        threshold = max(0.0, float(self.min_weight_change))
        prices = latest_prices or {}
        for symbol in sorted(set(previous) | set(target_weights)):
            old = float(previous.get(symbol, 0.0))
            new = float(target_weights.get(symbol, 0.0))
            if abs(new - old) < threshold:
                continue
            if abs(old) < threshold and abs(new) >= threshold:
                action = "APRI LONG" if new > 0 else "APRI SHORT"
            elif abs(new) < threshold:
                action = "CHIUDI"
            elif old * new < 0:
                action = "INVERTI LONG" if new > 0 else "INVERTI SHORT"
            elif abs(new) > abs(old):
                action = "AUMENTA"
            else:
                action = "RIDUCI"
            price_text = f" | prezzo indicativo {prices[symbol]:.2f}" if symbol in prices else ""
            changes.append(f"{action:12} {symbol:8} {old:+.1%} -> {new:+.1%}{price_text}")

        if not changes:
            return False
        body = (
            "Segnale di ribilanciamento (paper trading, non consulenza finanziaria).\n"
            f"Run: {run_id}\n\n" + "\n".join(changes) +
            "\n\nVerifica prezzi, liquidita e rischio prima di qualunque operazione."
        )
        sent = self._send_telegram(body)
        sent = self._send_email("[AI Hedge Fund] Segnale apri/chiudi posizioni", body) or sent
        if sent:
            self._save_weights(run_id, {k: float(v) for k, v in target_weights.items()})
        return sent
