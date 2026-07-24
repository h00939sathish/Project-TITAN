"""Root test configuration — marker registration and selective execution."""

import os
from pathlib import Path

import pytest


def _clean_titan_state():
    for pattern in (".titan_*.db", ".titan_*.json"):
        for p in Path.cwd().glob(pattern):
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass
    for d in (Path("src"),):
        for pattern in (".titan_*.db", ".titan_*.json"):
            for p in d.glob(pattern):
                try:
                    p.unlink(missing_ok=True)
                except Exception:
                    pass


_clean_titan_state()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Run tests requiring live Alpaca paper API credentials",
    )
    parser.addoption(
        "--run-paper-orders",
        action="store_true",
        default=False,
        help="Run tests that place real paper orders (one-share certification)",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    run_live = config.getoption("--run-live")
    run_orders = config.getoption("--run-paper-orders")
    skip_live = pytest.mark.skip(reason="Use --run-live to include live API tests")
    skip_benchmark = pytest.mark.skip(reason="Benchmark tests are not run in CI")
    skip_orders = pytest.mark.skip(reason="Use --run-paper-orders to include one-share paper order tests")
    for item in items:
        if "live" in item.keywords and not run_live:
            item.add_marker(skip_live)
        if "benchmark" in item.keywords:
            item.add_marker(skip_benchmark)
        if "paper_order" in item.keywords and not run_orders:
            item.add_marker(skip_orders)
