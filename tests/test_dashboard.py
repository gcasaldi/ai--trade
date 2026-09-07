from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace

import pandas as pd

from free_fund.dashboard import build_dashboard, write_dashboard
from scripts.build_pages import build


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.prices = pd.DataFrame({'AAPL': [100 + n for n in range(25)]}, index=pd.date_range('2026-08-01', periods=25))
        self.decision = SimpleNamespace(symbols=['AAPL'], target_weights={'AAPL': .25}, risk_flags=[], timestamp_utc=datetime.now(timezone.utc).isoformat())
        self.cfg = {'alerts': {'telegram_token': 'DO-NOT-PUBLISH', 'email_to': 'private@example.test', 'reference_capital': 12345}, 'portfolio': {'sector_by_symbol': {'AAPL': 'Technology'}}}

    def test_allowlist_and_real_price_date(self):
        result = build_dashboard(self.decision, self.prices, self.cfg)
        serialized = json.dumps(result)
        for private in ['DO-NOT-PUBLISH', 'private@example.test', '12345']:
            self.assertNotIn(private, serialized)
        self.assertEqual(result['price_date'], '2026-08-25')
        self.assertEqual(result['assets'][0]['reference_price_usd'], 124)
        self.assertAlmostEqual(result['assets'][0]['return_20d'], 124 / 104 - 1)
        self.assertFalse(result['ai_trader_integrated'])

    def test_failed_quality_never_ready(self):
        self.decision.risk_flags = ['data_quality_failed']
        self.assertEqual(build_dashboard(self.decision, self.prices, self.cfg)['status'], 'unavailable')

    def test_no_prices_serializes_without_nan(self):
        result = build_dashboard(self.decision, self.prices.iloc[:0], self.cfg)
        self.assertIsNone(result['assets'][0]['reference_price_usd'])
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'dashboard.json'
            write_dashboard(path, result)
            self.assertNotIn('NaN', path.read_text())

    def test_site_packages_no_other_output_files(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            secret = root / 'alert_state.json'
            secret.write_text('{"private": true}')
            build(Path(__file__).parents[1] / 'site', root / 'site', failed=True)
            self.assertEqual(json.loads((root / 'site/data.json').read_text())['status'], 'unavailable')
            self.assertEqual({p.name for p in (root / 'site').iterdir()}, {'index.html','styles.css','app.js','planner.js','data.json','.nojekyll'})
