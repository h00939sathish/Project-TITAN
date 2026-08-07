"""ADR-022 (F2 bypass) — enforcement: no registration-time qualification."""

import titan.strategies.registrations  # noqa: F401
from titan.strategies.registry import get_registry


def test_no_strategy_is_registered_qualified_adr022():
    """F2 bypass: no registered strategy may carry a non-empty
    qualified_variants at import. A baked-in variant is a fail-open bypass."""
    reg = get_registry()
    for sid in reg.list_ids():
        variant = reg.get(sid).qualified_variants
        assert not variant, (
            f"strategy '{sid}' has baked-in qualified_variants "
            f"{sorted(variant)} — ADR-022: qualification is gate-only."
        )
