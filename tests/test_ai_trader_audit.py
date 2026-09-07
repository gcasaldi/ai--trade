import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("audit_ai_trader", Path(__file__).parents[1] / "scripts/audit_ai_trader.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AuditTests(unittest.TestCase):
    def test_valid_operation_is_research_only(self):
        row = dict(symbol="MSFT", side="buy", entry_price=500, quantity=1,
                   executed_at="2026-09-07T10:00:00Z", market="us-stock", message_type="operation")
        report = module.audit({"signals": [row]}, {"MSFT"}, datetime(2026, 9, 7, 11, tzinfo=timezone.utc))
        self.assertEqual(report["eligible_for_research"], 1)
        self.assertFalse(report["operations"][0]["executable"])

    def test_copied_stale_invalid_operation_is_rejected(self):
        row = dict(symbol="BTC", side="short", entry_price=float("nan"), quantity=-1,
                   executed_at="2026-09-01T10:00:00Z", content="[Copied from trader]",
                   market="crypto", message_type="operation")
        report = module.audit({"signals": [row]}, {"MSFT"}, datetime(2026, 9, 7, tzinfo=timezone.utc))
        self.assertEqual(report["eligible_for_research"], 0)
        self.assertEqual(len(report["operations"][0]["reasons"]), 7)

    def test_malformed_payload_fails(self):
        with self.assertRaises(ValueError):
            module.audit({"signals": [None]}, set(), datetime.now(timezone.utc))

    def test_naive_timestamp_rejected(self):
        report = module.audit({"signals": [{"executed_at": "2026-09-07T10:00:00"}]}, set(), datetime.now(timezone.utc))
        self.assertIn("invalid_execution_time", report["operations"][0]["reasons"])
