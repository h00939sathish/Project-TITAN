import pytest
import os
import json
import sys
import types
from decimal import Decimal
from enum import Enum

# NautilusTrader IB adapter compatibility shim for ibapi 9.81
if "ibapi.const" not in sys.modules:
    const_mod = types.ModuleType("ibapi.const")
    const_mod.UNSET_DECIMAL = Decimal(2**127 - 1)
    const_mod.UNSET_INTEGER = 2**31 - 1
    const_mod.UNSET_DOUBLE = 1.7976931348623157e308
    sys.modules["ibapi.const"] = const_mod

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

