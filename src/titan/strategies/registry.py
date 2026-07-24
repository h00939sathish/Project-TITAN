import json
from dataclasses import dataclass
from typing import Callable

from titan.strategies.timeframes import Timeframe


@dataclass(frozen=True)
class ParameterDef:
    name: str
    type_name: str
    default: float | int | str
    description: str = ""


@dataclass(frozen=True)
class StrategyRegistration:
    strategy_id: str
    version: str
    description: str
    parameter_schema: tuple[ParameterDef, ...]
    factory: Callable[[dict], Callable]
    qualified_variants: frozenset[tuple[Timeframe, str]] = frozenset()

    def is_qualified_for(self, timeframe: Timeframe, params: dict) -> bool:
        return (timeframe, json.dumps(params, sort_keys=True)) in self.qualified_variants


class StrategyRegistry:
    def __init__(self):
        self._strategies: dict[str, StrategyRegistration] = {}

    def register(self, reg: StrategyRegistration) -> None:
        if reg.strategy_id in self._strategies:
            raise ValueError(f"Strategy '{reg.strategy_id}' already registered")
        self._strategies[reg.strategy_id] = reg

    def get(self, strategy_id: str) -> StrategyRegistration:
        if strategy_id not in self._strategies:
            raise KeyError(
                f"Unknown strategy '{strategy_id}'. "
                f"Registered: {', '.join(sorted(self._strategies))}"
            )
        return self._strategies[strategy_id]

    def list_ids(self) -> list[str]:
        return sorted(self._strategies)


_REGISTRY = StrategyRegistry()


def get_registry() -> StrategyRegistry:
    return _REGISTRY
