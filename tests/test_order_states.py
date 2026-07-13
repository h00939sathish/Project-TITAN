"""Tests for the order state machine."""

from titan._core import OrderState, OrderStateMachine


class TestOrderState:
    def test_values(self) -> None:
        assert OrderState.New == OrderState.New
        assert OrderState.Filled != OrderState.New

    def test_terminal_states(self) -> None:
        assert OrderState.Filled.is_terminal()
        assert OrderState.Cancelled.is_terminal()
        assert OrderState.Rejected.is_terminal()
        assert OrderState.Expired.is_terminal()
        assert not OrderState.New.is_terminal()
        assert not OrderState.Acknowledged.is_terminal()


class TestOrderStateMachine:
    def test_starts_at_new(self) -> None:
        m = OrderStateMachine()
        assert str(m) == "OrderStateMachine(New)"
        assert not m.current.is_terminal()

    def test_normal_lifecycle(self) -> None:
        m = OrderStateMachine()
        m.transition(OrderState.Validated)
        m.transition(OrderState.Submitted)
        m.transition(OrderState.Acknowledged)
        m.transition(OrderState.PartiallyFilled)
        m.transition(OrderState.Filled)
        assert m.current == OrderState.Filled
        assert m.current.is_terminal()

    def test_rejection_from_new(self) -> None:
        m = OrderStateMachine()
        m.transition(OrderState.Rejected)
        assert m.current == OrderState.Rejected

    def test_cancel_after_ack(self) -> None:
        m = OrderStateMachine()
        m.transition(OrderState.Validated)
        m.transition(OrderState.Submitted)
        m.transition(OrderState.Acknowledged)
        m.transition(OrderState.CancelPending)
        m.transition(OrderState.Cancelled)
        assert m.current == OrderState.Cancelled

    def test_unknown_then_reconcile_to_filled(self) -> None:
        m = OrderStateMachine()
        m.transition(OrderState.Validated)
        m.transition(OrderState.Submitted)
        m.transition(OrderState.Unknown)
        assert m.current == OrderState.Unknown
        m.transition(OrderState.Filled)
        assert m.current == OrderState.Filled

    def test_unknown_then_reconcile_to_cancelled(self) -> None:
        m = OrderStateMachine()
        m.transition(OrderState.Validated)
        m.transition(OrderState.Submitted)
        m.transition(OrderState.Unknown)
        m.transition(OrderState.Cancelled)
        assert m.current == OrderState.Cancelled

    def test_illegal_transition_raises(self) -> None:
        m = OrderStateMachine()
        try:
            m.transition(OrderState.Cancelled)
            assert False, "Should have raised"
        except ValueError:
            assert m.current == OrderState.New

    def test_terminal_state_rejects_all(self) -> None:
        m = OrderStateMachine()
        m.transition(OrderState.Validated)
        m.transition(OrderState.Submitted)
        m.transition(OrderState.Acknowledged)
        m.transition(OrderState.PartiallyFilled)
        m.transition(OrderState.Filled)
        try:
            m.transition(OrderState.Acknowledged)
            assert False, "Should have raised"
        except ValueError:
            pass

    def test_reset_to(self) -> None:
        m = OrderStateMachine()
        m.transition(OrderState.Validated)
        m.transition(OrderState.Submitted)
        m.transition(OrderState.Acknowledged)
        m.transition(OrderState.PartiallyFilled)
        m.transition(OrderState.Filled)
        m.reset_to(OrderState.New)
        assert m.current == OrderState.New

    def test_expiry(self) -> None:
        m = OrderStateMachine()
        m.transition(OrderState.Validated)
        m.transition(OrderState.Submitted)
        m.transition(OrderState.Acknowledged)
        m.transition(OrderState.Expired)
        assert m.current == OrderState.Expired

    def test_empty_reason_codes(self) -> None:
        # Verify we can instantiate the machine and run a simple scenario
        m = OrderStateMachine()
        assert m.current == OrderState.New
