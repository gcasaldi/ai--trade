from __future__ import annotations

import json

from free_fund.alerts import AlertManager
from free_fund.config import load_config


class FakeSMTP:
    sent = []

    def __init__(self, host, port, timeout):
        self.host = host
        self.port = port

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def starttls(self, context):
        return None

    def login(self, username, password):
        assert username == "sender@example.com"
        assert password == "secret"

    def send_message(self, message):
        self.sent.append(message)


def test_position_email_is_classified_and_deduplicated(monkeypatch, tmp_path):
    FakeSMTP.sent.clear()
    monkeypatch.setenv("ALERT_SMTP_USER", "sender@example.com")
    monkeypatch.setenv("ALERT_SMTP_APP_PASSWORD", "secret")
    monkeypatch.setattr("free_fund.alerts.smtplib.SMTP", FakeSMTP)
    state = tmp_path / "alert_state.json"
    manager = AlertManager(enabled=True, email_to="recipient@example.com", state_path=state)

    assert manager.notify_position_changes("run-1", {"SPY": 0.30}, {"SPY": 101.5})
    assert "COMPRA" in FakeSMTP.sent[-1].get_content()
    assert "stop 99.47" in FakeSMTP.sent[-1].get_content()
    assert "obiettivo 105.56" in FakeSMTP.sent[-1].get_content()
    assert not manager.notify_position_changes("run-2", {"SPY": 0.30}, {"SPY": 102.0})
    assert len(FakeSMTP.sent) == 1

    assert manager.notify_position_changes("run-3", {"SPY": 0.0}, {"SPY": 99.0})
    assert "CHIUDI" in FakeSMTP.sent[-1].get_content()
    assert json.loads(state.read_text())["target_weights"]["SPY"] == 0.0


def test_missing_credentials_does_not_consume_signal(monkeypatch, tmp_path):
    monkeypatch.delenv("ALERT_SMTP_USER", raising=False)
    monkeypatch.delenv("ALERT_SMTP_APP_PASSWORD", raising=False)
    state = tmp_path / "alert_state.json"
    manager = AlertManager(enabled=True, email_to="recipient@example.com", state_path=state)

    assert not manager.notify_position_changes("run-1", {"QQQ": 0.25})
    assert not state.exists()


def test_telegram_delivery_works_without_email(monkeypatch, tmp_path):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    calls = []
    monkeypatch.delenv("ALERT_SMTP_USER", raising=False)
    monkeypatch.delenv("ALERT_SMTP_APP_PASSWORD", raising=False)
    monkeypatch.setenv("ALERT_TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("ALERT_TELEGRAM_CHAT_ID", "12345")
    monkeypatch.setattr(
        "free_fund.alerts.requests.post",
        lambda url, json, timeout: calls.append((url, json)) or Response(),
    )
    state = tmp_path / "alert_state.json"
    manager = AlertManager(enabled=True, state_path=state)

    assert manager.notify_position_changes("run-1", {"SPY": 0.30})
    assert calls[0][0].endswith("/sendMessage")
    assert calls[0][1]["chat_id"] == "12345"
    assert "COMPRA" in calls[0][1]["text"]
    assert state.exists()


def test_live_advisor_config_preserves_long_only():
    config = load_config("configs/live_stub.yaml")

    assert config["portfolio"]["long_only"] is True
    assert config["portfolio"]["max_weight"] == 0.25
    assert config["portfolio"]["gross_limit"] == 0.75
    assert config["runtime"]["pipeline_mode"] is False
