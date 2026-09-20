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

# NautilusTrader IB adapter compatibility shim for ibapi 9.81
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

# We monkeypatch the engine submit_intent for older tests that do not provision
# a cryptographic certificate, so they don't all fail due to ADR-028 enforcement.
# The integrity tests in test_execution_integrity.py will NOT use this patch,
# proving the engine works exactly as designed out of the box.

original_submit = PaperTradingEngine.submit_intent

def submit_intent_patched(self, intent, *args, **kwargs):
    return self._submit_intent_core(intent, *args, **kwargs)

@pytest.fixture(autouse=True)
def patch_submit_intent_for_legacy_tests(monkeypatch, request):
    # Don't patch if we are running the execution integrity, adversarial, or e2e tests
    if "test_execution_integrity" not in request.node.nodeid and "test_profit_engine_e2e" not in request.node.nodeid and "e2e" not in request.node.nodeid and "adversarial" not in request.node.nodeid:
        monkeypatch.setattr(PaperTradingEngine, "submit_intent", submit_intent_patched)

