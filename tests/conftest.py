import pytest
import os
import json
import sys
import types
from decimal import Decimal
from enum import Enum


def pytest_addoption(parser):
    parser.addoption("--run-paper-orders", action="store_true", default=False,
                     help="run tests marked paper_order (place real Alpaca paper orders)")
    parser.addoption("--run-live", action="store_true", default=False,
                     help="run tests marked live (hit the real Alpaca API)")


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "paper_order" in item.keywords and not config.getoption("--run-paper-orders"):
            item.add_marker(pytest.mark.skip(
                reason="places real paper orders; requires --run-paper-orders (and US regular session hours)"))
        if "live" in item.keywords and not config.getoption("--run-live"):
            item.add_marker(pytest.mark.skip(
                reason="requires live Alpaca API; run with --run-live"))

# IB adapter compatibility shim for ibapi 9.81
try:
    import ibapi.const
except ImportError:
    pass

if "ibapi.const" not in sys.modules:
    const_mod = types.ModuleType("ibapi.const")
    sys.modules["ibapi.const"] = const_mod

const_mod = sys.modules["ibapi.const"]
if not hasattr(const_mod, "UNSET_DECIMAL"):
    const_mod.UNSET_DECIMAL = Decimal(2**127 - 1)
if not hasattr(const_mod, "UNSET_INTEGER"):
    const_mod.UNSET_INTEGER = 2**31 - 1
if not hasattr(const_mod, "UNSET_DOUBLE"):
    const_mod.UNSET_DOUBLE = 1.7976931348623157e308
if not hasattr(const_mod, "NO_VALID_ID"):
    const_mod.NO_VALID_ID = -1

try:
    import ibapi.contract
    if not hasattr(ibapi.contract, "FundAssetType"):
        class FundAssetType(Enum):
            NoneItem = "None"
            OTHERS = "000"
        ibapi.contract.FundAssetType = FundAssetType

    if not hasattr(ibapi.contract, "FundDistributionPolicyIndicator"):
        class FundDistributionPolicyIndicator(Enum):
            NoneItem = "None"
            NONE = "N"
        ibapi.contract.FundDistributionPolicyIndicator = FundDistributionPolicyIndicator
except ImportError:
    pass

try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    _TEST_PRIV = ed25519.Ed25519PrivateKey.from_private_bytes(b"TITAN_TEST_ED25519_KEY_32_BYTES!")
    os.environ["TITAN_EXEC_PUBKEY"] = _TEST_PRIV.public_key().public_bytes_raw().hex()
except ImportError:
    pass

from titan.execution.engine import PaperTradingEngine


def certify(intent):
    """Return `intent` re-issued with a test-key certificate scoped exactly to it."""
    from dataclasses import asdict
    from titan._core import TradeIntent
    from titan.research.promotion_certificate import (
        create_signed_certificate, execution_scope_parameters)

    scope = execution_scope_parameters(
        instrument=intent.instrument_id, side=intent.side,
        max_quantity=int(Decimal(intent.quantity)), account=intent.account_id)
    cert = create_signed_certificate(_TEST_PRIV, intent.strategy_id, "2099-01-01T00:00:00Z",
                                     parameters=scope)
    # Constructor, not from_json: from_json re-validates fields, and tests behind the
    # gate deliberately submit malformed timestamps/prices for the engine to reject.
    return TradeIntent(
        intent.strategy_id, intent.strategy_package_digest, intent.account_id,
        intent.instrument_id, intent.side, intent.quantity, intent.order_type,
        intent.time_in_force, intent.risk_profile_version, intent.market_data_timestamp,
        price=intent.price, stop_price=intent.stop_price,
        take_profit_price=intent.take_profit_price, trailing=intent.trailing,
        expiry=intent.expiry, certificate_ref=json.dumps(asdict(cert)))


@pytest.fixture
def sign_uncertified_intents(monkeypatch):
    """Opt-in for tests about engine behaviour behind the gate, not the gate itself.

    Intents with no certificate, or a placeholder string such as "test-cert", get a
    real signed certificate and then pass through the real submit_intent, so
    signature, scope and nonce checks all still run. Intents carrying a JSON
    certificate object, forged or not, are passed through untouched.
    """
    real_submit = PaperTradingEngine.submit_intent

    def is_certificate_object(ref):
        try:
            return isinstance(json.loads(ref), dict)
        except (TypeError, ValueError):
            return False

    def submit(self, intent, *args, **kwargs):
        if not is_certificate_object(getattr(intent, "certificate_ref", None)):
            intent = certify(intent)
        return real_submit(self, intent, *args, **kwargs)

    monkeypatch.setattr(PaperTradingEngine, "submit_intent", submit)

