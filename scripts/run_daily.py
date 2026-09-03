from __future__ import annotations

import argparse

from free_fund.config import load_config
from free_fund.env_utils import load_dotenv_file
from free_fund.orchestrator import CentralizedHedgeFundSystem


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='configs/default.yaml')
    parser.add_argument('--dry-run', action='store_true', help='Skip broker order submission.')
    parser.add_argument(
        '--require-alert',
        action='store_true',
        help='Fail when this cycle does not deliver its expected advisory message.',
    )
    args = parser.parse_args()

    load_dotenv_file()
    cfg = load_config(args.config)
    system = CentralizedHedgeFundSystem(cfg)
    decision = system.run_cycle(execute=not args.dry_run)
    if args.require_alert and not getattr(system, 'last_position_alert_sent', False):
        raise RuntimeError('The expected Telegram advisory message was not delivered')

    portfolio = cfg.get("portfolio", {})
    if portfolio.get("long_only", False):
        tolerance = 1e-9
        max_weight = float(portfolio.get("max_weight", 1.0))
        gross_limit = float(portfolio.get("gross_limit", 1.0))
        weights = [float(value) for value in decision.target_weights.values()]
        if any(value < -tolerance or value > max_weight + tolerance for value in weights):
            raise RuntimeError("Unsafe advisor output: position violates long-only/max-weight limits")
        if sum(weights) > gross_limit + tolerance:
            raise RuntimeError("Unsafe advisor output: gross exposure exceeds configured limit")

    print(f'run_id: {decision.run_id}')
    print('weights:')
    for symbol, weight in decision.target_weights.items():
        print(f'  {symbol}: {weight:.6f}')
    if decision.risk_flags:
        print('risk_flags:', ', '.join(decision.risk_flags))


if __name__ == '__main__':
    main()
