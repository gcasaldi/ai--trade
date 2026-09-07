"""Optional UI smoke test: python tests/browser_dashboard_smoke.py (Chrome + playwright)."""
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

from playwright.sync_api import sync_playwright


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    root = Path(__file__).resolve().parents[1]
    handler = partial(QuietHandler, directory=str(root / '_site'))
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    Thread(target=server.serve_forever, daemon=True).start()
    now = datetime.now(timezone.utc)
    payload = {'schema_version': 1, 'status': 'ready', 'decision_at': now.isoformat(),
               'price_date': now.date().isoformat(), 'max_price_age_hours': 48, 'rules': {},
               'assets': [{'symbol': 'AAPL', 'target_weight': .25, 'reference_price_usd': 100,
                           'return_20d': .02, 'reasons': ['Synthetic UI test only'], 'source_urls': []},
                          {'symbol': 'MSFT', 'target_weight': 0, 'reference_price_usd': 200,
                           'return_20d': -.01, 'reasons': [], 'source_urls': []}]}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='chrome', headless=True)
            page = browser.new_page(viewport={'width': 1440, 'height': 1100})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.route('**/data.json?*', lambda route: route.fulfill(content_type='application/json', body=json.dumps(payload)))
            page.goto(f'http://127.0.0.1:{server.server_port}/', wait_until='networkidle')
            assert page.locator('.card').count() == 2
            assert 'ANALISI DISPONIBILE' in page.locator('#status-pill').inner_text()
            assert '25,00' in page.locator('.action-amount').first.inner_text()
            page.locator('#holdings summary').click()
            page.locator('#holding-MSFT-amount').fill('30')
            page.locator('[data-filter="sell"]').click()
            assert page.locator('.card').count() == 1
            assert 'MSFT' in page.locator('.asset-name').inner_text()
            page.locator('[data-filter="all"]').click()
            page.screenshot(path=str(root / '.venv/dashboard-desktop.png'), full_page=True)
            page.locator('#capital').fill('10')
            assert page.locator('.pill.buy,.pill.sell').count() == 0
            page.locator('#capital').fill('100')
            payload['price_date'] = '2000-01-01'
            page.locator('#refresh').click()
            page.wait_for_function("document.querySelector('#status-pill').textContent === 'DATI DA AGGIORNARE'")
            assert page.locator('.pill.buy,.pill.sell').count() == 0
            page.set_viewport_size({'width': 390, 'height': 844})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(root / '.venv/dashboard-mobile.png'), full_page=True)
            page.locator('#reset').click()
            assert json.loads(page.evaluate("localStorage.getItem('osservatorio-portfolio-v1')"))['holdings'] == {}
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
    print('Browser checks passed: desktop, mobile, holdings, sell filter, invalid capital, stale data, reset.')


if __name__ == '__main__':
    main()
