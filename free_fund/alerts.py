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

ASSET_NAMES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc. - Classe A",
    "META": "Meta Platforms, Inc. - Classe A",
    "JPM": "JPMorgan Chase & Co.",
    "JNJ": "Johnson & Johnson",
    "PG": "Procter & Gamble Company",
    "XOM": "Exxon Mobil Corporation",
    "HD": "Home Depot, Inc.",
    "KO": "Coca-Cola Company",
    "V": "Visa Inc. - Classe A",
    "LLY": "Eli Lilly and Company",
    "CAT": "Caterpillar Inc.",
    "GE": "GE Aerospace",
    "CVX": "Chevron Corporation",
    "LIN": "Linde plc",
    "NEM": "Newmont Corporation",
    "NEE": "NextEra Energy, Inc.",
    "DUK": "Duke Energy Corporation",
    "AMT": "American Tower Corporation",
    "PLD": "Prologis, Inc.",
    "SPY": "SPDR S&P 500 ETF Trust",
    "QQQ": "Invesco QQQ Trust - Nasdaq 100",
    "IWM": "iShares Russell 2000 ETF",
    "TLT": "iShares 20+ Year Treasury Bond ETF",
    "GLD": "SPDR Gold Shares",
}

ASSET_SECTORS = {
    "AAPL": "Tecnologia", "MSFT": "Tecnologia", "NVDA": "Tecnologia",
    "GOOGL": "Comunicazioni", "META": "Comunicazioni",
    "AMZN": "Consumi discrezionali", "HD": "Consumi discrezionali",
    "PG": "Beni di prima necessita", "KO": "Beni di prima necessita",
    "JPM": "Finanza", "V": "Finanza", "JNJ": "Salute", "LLY": "Salute",
    "CAT": "Industria", "GE": "Industria", "XOM": "Energia", "CVX": "Energia",
    "LIN": "Materiali", "NEM": "Materiali", "NEE": "Servizi pubblici",
    "DUK": "Servizi pubblici", "AMT": "Immobiliare", "PLD": "Immobiliare",
}


def asset_label(symbol: str) -> str:
    name = ASSET_NAMES.get(symbol.upper())
    return f"{name} ({symbol})" if name else symbol


def asset_details(symbol: str) -> str:
    sector = ASSET_SECTORS.get(symbol.upper(), "Non classificato")
    return f"Titolo: {asset_label(symbol)}\nSettore: {sector}"


def money(value: float) -> str:
    return f"EUR {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def usd_price(value: float) -> str:
    return f"USD {value:.2f}".replace(".", ",")


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
    estimated_tax_rate: float = 0.26
    commission_per_order: float = 1.0
    minimum_net_profit_pct: float = 0.02

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
                json={"chat_id": chat_id, "text": text, "protect_content": True},
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
                "ledger": {},
                "last_summary_date": "",
                "last_summary_slot": "",
            }
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            return {
                "state_version": int(raw.get("state_version", 1)),
                "target_weights": {
                    str(k): float(v) for k, v in raw.get("target_weights", {}).items()
                },
                "model_positions": dict(raw.get("model_positions", {}) or {}),
                "ledger": dict(raw.get("ledger", {}) or {}),
                "last_summary_date": str(raw.get("last_summary_date", "")),
                "last_summary_slot": str(raw.get("last_summary_slot", "")),
            }
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return {
                "state_version": 1,
                "target_weights": {},
                "model_positions": {},
                "ledger": {},
                "last_summary_date": "",
                "last_summary_slot": "",
            }

    def _save_state(
        self,
        run_id: str,
        weights: dict[str, float],
        positions: dict[str, dict[str, Any]],
        ledger: dict[str, float],
        last_summary_date: str,
        last_summary_slot: str,
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
                    "ledger": ledger,
                    "last_summary_date": last_summary_date,
                    "last_summary_slot": last_summary_slot,
                },
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def _record_sale(
        self,
        ledger: dict[str, float],
        invested_amount: float,
        entry_price: float,
        sale_price: float,
        commissions: float,
    ) -> tuple[float, float, float, float]:
        gross = invested_amount * ((sale_price / entry_price) - 1.0) if entry_price > 0 else 0.0
        fees = max(0.0, commissions)
        taxable_gain = max(0.0, gross - fees)
        tax = taxable_gain * max(0.0, float(self.estimated_tax_rate))
        net = gross - fees - tax
        ledger["realized_gross"] = float(ledger.get("realized_gross", 0.0)) + gross
        ledger["commissions"] = float(ledger.get("commissions", 0.0)) + fees
        ledger["estimated_tax"] = float(ledger.get("estimated_tax", 0.0)) + tax
        ledger["realized_net"] = float(ledger.get("realized_net", 0.0)) + net
        ledger["sales"] = float(ledger.get("sales", 0.0)) + 1.0
        return gross, fees, tax, net

    def _minimum_profitable_target(
        self,
        entry_price: float,
        invested_amount: float,
        buy_fees: float,
    ) -> float:
        future_fees = max(0.0, buy_fees) + max(0.0, float(self.commission_per_order))
        desired_net = invested_amount * max(0.0, float(self.minimum_net_profit_pct))
        after_tax_share = max(0.01, 1.0 - max(0.0, float(self.estimated_tax_rate)))
        required_gain = future_fees + (desired_net / after_tax_share)
        target_pct = max(
            max(0.0, float(self.take_profit_pct)),
            required_gain / invested_amount if invested_amount > 0 else 0.0,
        )
        return entry_price * (1.0 + target_pct)

    @staticmethod
    def _sale_result_text(
        gross: float, fees: float, tax: float, net: float, ledger: dict[str, float]
    ) -> str:
        return (
            "\n\nRISULTATO STIMATO DELLA VENDITA"
            f"\nPrima delle tasse: {money(gross)}"
            f"\nCommissioni di acquisto e vendita: {money(fees)}"
            f"\nTasse italiane stimate (26%): {money(tax)}"
            f"\nDopo le tasse stimate: {money(net)}"
            f"\nTotale netto dall'inizio: {money(float(ledger.get('realized_net', 0.0)))}"
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
        ledger: dict[str, float] = state["ledger"]
        model_capital = max(
            0.0,
            float(self.reference_capital) + float(ledger.get("realized_net", 0.0)),
        )
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
            invested = float(
                position.get(
                    "invested_amount",
                    float(position.get("target_weight", 0.0)) * self.reference_capital,
                )
            )
            buy_fees = float(position.get("buy_fees", self.commission_per_order))
            target = max(
                float(position["target_price"]),
                self._minimum_profitable_target(entry, invested, buy_fees),
            )
            position["target_price"] = target
            position["buy_fees"] = buy_fees
            if price <= stop:
                fees = float(position.get("buy_fees", self.commission_per_order)) + float(
                    self.commission_per_order
                )
                gross, fees, tax, net = self._record_sale(ledger, invested, entry, price, fees)
                changes.append(
                    f"COSA FARE: VENDI TUTTO\n{asset_details(symbol)}\n"
                    f"Motivo: il prezzo e sceso al limite di sicurezza.\n"
                    f"Prezzo di ingresso: {usd_price(entry)}\nPrezzo attuale: {usd_price(price)}"
                    + self._sale_result_text(gross, fees, tax, net, ledger)
                )
                exited_symbols.add(symbol)
                del positions[symbol]
            elif price >= target:
                fees = float(position.get("buy_fees", self.commission_per_order)) + float(
                    self.commission_per_order
                )
                gross, fees, tax, net = self._record_sale(ledger, invested, entry, price, fees)
                changes.append(
                    f"COSA FARE: VENDI TUTTO\n{asset_details(symbol)}\n"
                    f"Motivo: il prezzo ha raggiunto l'obiettivo di guadagno.\n"
                    f"Prezzo di ingresso: {usd_price(entry)}\nPrezzo attuale: {usd_price(price)}"
                    + self._sale_result_text(gross, fees, tax, net, ledger)
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
            amount = max(0.0, new) * model_capital
            line = f"COSA FARE: {action}\n{asset_details(symbol)}\n"
            if action in {"COMPRA", "COMPRA ANCORA"}:
                line += f"Budget totale suggerito: {money(amount)}"
            elif action == "VENDI UNA PARTE":
                line += f"Dopo la vendita lascia investiti: {money(amount)}"
            else:
                line += "Quantita da lasciare investita: zero"
            if price is not None:
                line += f"\nPrezzo attuale del titolo: {usd_price(price)}"
                if action in {"COMPRA", "COMPRA ANCORA"} and new > 0:
                    existing = positions.get(symbol, {})
                    existing_amount = float(existing.get("invested_amount", 0.0))
                    added_amount = max(0.0, new - max(0.0, old)) * model_capital
                    total_amount = existing_amount + added_amount
                    existing_buy_fees = float(existing.get("buy_fees", 0.0))
                    added_buy_fee = float(self.commission_per_order) if added_amount > 0 else 0.0
                    total_buy_fees = existing_buy_fees + added_buy_fee
                    existing_entry = float(existing.get("entry_price", price))
                    average_entry = (
                        ((existing_entry * existing_amount) + (price * added_amount)) / total_amount
                        if total_amount > 0
                        else price
                    )
                    stop = average_entry * (1.0 - max(0.0, float(self.stop_loss_pct)))
                    target = self._minimum_profitable_target(
                        average_entry,
                        total_amount,
                        total_buy_fees,
                    )
                    entry_low = price * 0.9975
                    entry_high = price * 1.0025
                    line += (
                        f"\nEntra solo tra: {usd_price(entry_low)} e {usd_price(entry_high)}"
                        f"\nStop, vendi se scende a: {usd_price(stop)}"
                        f"\nObiettivo, valuta la vendita a: {usd_price(target)}"
                    )
                    positions[symbol] = {
                        "entry_price": average_entry,
                        "stop_price": stop,
                        "target_price": target,
                        "target_weight": new,
                        "invested_amount": total_amount,
                        "buy_fees": total_buy_fees,
                        "opened_run_id": run_id,
                    }
                elif action in {"VENDI UNA PARTE", "VENDI TUTTO"} and symbol in positions:
                    position = positions[symbol]
                    entry = float(position["entry_price"])
                    current_amount = float(
                        position.get("invested_amount", max(0.0, old) * self.reference_capital)
                    )
                    remaining_amount = max(0.0, new) * model_capital
                    sold_amount = current_amount if action == "VENDI TUTTO" else max(
                        0.0, current_amount - remaining_amount
                    )
                    current_buy_fees = float(position.get("buy_fees", self.commission_per_order))
                    sold_fraction = min(1.0, sold_amount / current_amount) if current_amount > 0 else 0.0
                    allocated_buy_fees = current_buy_fees * sold_fraction
                    fees = allocated_buy_fees + max(0.0, float(self.commission_per_order))
                    gross, fees, tax, net = self._record_sale(
                        ledger, sold_amount, entry, price, fees
                    )
                    line += self._sale_result_text(gross, fees, tax, net, ledger)
                    if action == "VENDI UNA PARTE":
                        position["invested_amount"] = remaining_amount
                        position["target_weight"] = new
                        position["buy_fees"] = current_buy_fees - allocated_buy_fees
            if action == "VENDI TUTTO":
                positions.pop(symbol, None)
            changes.append(line)

        now_italy = datetime.now(timezone.utc).astimezone()
        today = now_italy.date().isoformat()
        summary_period = "sera" if now_italy.hour >= 19 else "mattina"
        summary_slot = f"{today}:{summary_period}"
        # Add a quiet morning check-in when there is no trade. The evening
        # report is always complete, even if the same cycle has an action.
        should_add_summary = state["last_summary_slot"] != summary_slot and (
            not changes or summary_period == "sera"
        )
        if should_add_summary:
            if positions:
                open_net_total = 0.0
                for symbol, position in sorted(positions.items()):
                    price = float(prices.get(symbol, position["entry_price"]))
                    entry = float(position["entry_price"])
                    pnl = (price / entry - 1.0) if entry > 0 else 0.0
                    invested = float(position.get("invested_amount", 0.0))
                    open_gross = invested * pnl
                    estimated_fees = float(position.get("buy_fees", self.commission_per_order)) + max(
                        0.0, float(self.commission_per_order)
                    )
                    open_tax = max(0.0, open_gross - estimated_fees) * max(
                        0.0, float(self.estimated_tax_rate)
                    )
                    open_net = open_gross - estimated_fees - open_tax
                    open_net_total += open_net
                    changes.append(
                        f"COSA FARE: MANTIENI\n{asset_details(symbol)}\n"
                        f"Prezzo di ingresso: {usd_price(entry)}\n"
                        f"Prezzo attuale: {usd_price(price)}\n"
                        f"Rendimento: {pnl:+.1%}\n"
                        f"Risultato aperto netto stimato: {money(open_net)}\n"
                        f"Stop, vendi se scende a: {usd_price(float(position['stop_price']))}\n"
                        f"Obiettivo, valuta la vendita a: {usd_price(float(position['target_price']))}"
                    )
                changes.append(
                    "RIEPILOGO DEL PORTAFOGLIO MODELLO\n"
                    f"Risultato gia incassato: {money(float(ledger.get('realized_net', 0.0)))}\n"
                    f"Risultato ancora aperto: {money(open_net_total)}"
                )
            else:
                changes.append(
                    "Per ora restiamo tranquilli: il modello non vede un acquisto "
                    "abbastanza prudente da fare. Ti avviso appena cambia qualcosa."
                )

        if not changes:
            return False
        greeting = (
            "Buongiorno. Ho controllato il mercato: ecco cosa farei oggi."
            if summary_period == "mattina"
            else "Buonasera. Ecco il report completo di oggi."
        )
        body = (
            greeting + "\n\n"
            + "\n\n--------------------\n\n".join(changes) +
            "\n\nNota: prezzi dei titoli in dollari, budget in euro. Il bot non esegue ordini. "
            "Per budget piccoli il broker deve supportare azioni frazionate e conversione valuta. "
            "Niente leva, short o cripto. Tasse al 26% stimate: fa fede il broker."
        )
        sent = self._send_telegram(body)
        sent = self._send_email("[AI Hedge Fund] Segnale apri/chiudi posizioni", body) or sent
        if sent:
            saved_weights = {k: float(v) for k, v in target_weights.items()}
            # An automatic stop/target closes the model position. Saving it as
            # flat lets a still-valid signal propose a fresh entry next cycle.
            for symbol in exited_symbols:
                saved_weights[symbol] = 0.0
            self._save_state(
                run_id,
                saved_weights,
                positions,
                ledger,
                today,
                summary_slot,
            )
        return sent
