import os, sys, threading, time
from decimal import Decimal
from nautilus_trader.adapters.interactive_brokers.common import IB, IB_VENUE
from nautilus_trader.adapters.interactive_brokers.config import (
    IBMarketDataTypeEnum,
    InteractiveBrokersDataClientConfig,
    InteractiveBrokersExecClientConfig,
    InteractiveBrokersInstrumentProviderConfig,
    SymbologyMethod,
)
from nautilus_trader.adapters.interactive_brokers.factories import (
    InteractiveBrokersLiveDataClientFactory,
    InteractiveBrokersLiveExecClientFactory,
)
from nautilus_trader.config import (
    LoggingConfig,
    RoutingConfig,
    StrategyConfig,
    TradingNodeConfig,
    LiveDataEngineConfig,
)
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide, TimeInForce
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.trading.strategy import Strategy


IB_HOST = "127.0.0.1"
IB_PORT = 7497
DATA_CLIENT_ID = int(os.getenv("IB_DATA_CLIENT_ID", "1201"))
EXEC_CLIENT_ID = int(os.getenv("IB_EXEC_CLIENT_ID", "1202"))
ACCOUNT_ID = os.getenv("TWS_ACCOUNT", "DUQ284074")
TRADE_SIZE = Decimal(os.getenv("TRADE_SIZE", "10000"))  # base currency units (0.1 lot for EUR/USD)
LOOKBACK = int(os.getenv("LOOKBACK", "20"))
AUTO_STOP_SECS = int(os.getenv("AUTO_STOP_SECS", "0"))


class MomConfig(StrategyConfig, kw_only=True, frozen=True):
    instrument_id: InstrumentId
    bar_type: BarType
    trade_size: Decimal
    lookback: int = 20


class MomStrategy(Strategy):
    def __init__(self, config: MomConfig) -> None:
        super().__init__(config)
        self.prices: list[float] = []

    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        if self.instrument is None:
            self.log.error(f"Instrument not found: {self.config.instrument_id}")
            self.stop()
            return
        self.log.info(f"Starting Momentum({self.config.lookback}) on {self.config.instrument_id}, trade_size={self.config.trade_size}")
        self.subscribe_bars(self.config.bar_type)

    def on_bar(self, bar: Bar) -> None:
        close = float(bar.close.as_double())
        self.prices.append(close)

        if len(self.prices) < self.config.lookback + 1:
            return

        n_day_ret = (self.prices[-1] - self.prices[-(self.config.lookback + 1)]) / self.prices[-(self.config.lookback + 1)]
        flat = self.portfolio.is_flat(self.config.instrument_id)

        self.log.info(f"Bar close={close:.2f} ret={n_day_ret:.4f} flat={flat}")

        if n_day_ret > 0 and flat:
            order = self.order_factory.market(
                instrument_id=self.config.instrument_id,
                order_side=OrderSide.BUY,
                quantity=self.instrument.make_qty(self.config.trade_size),
                time_in_force=TimeInForce.GTC,
            )
            self.submit_order(order)
            self.log.info(f"BUY {self.config.trade_size} units")
        elif n_day_ret < 0 and not flat:
            self.close_all_positions(self.config.instrument_id)
            self.log.info("CLOSE all positions")

    def on_stop(self) -> None:
        self.log.info("Strategy stopping — exiting all positions")
        self.cancel_all_orders(self.config.instrument_id)
        self.close_all_positions(self.config.instrument_id)


def main():
    instrument_id = InstrumentId.from_str("EUR/USD.IDEALPRO")
    bar_type = BarType.from_str("EUR/USD.IDEALPRO-1-DAY-LAST-EXTERNAL")

    inst_provider = InteractiveBrokersInstrumentProviderConfig(
        symbology_method=SymbologyMethod.IB_SIMPLIFIED,
        load_ids=frozenset([str(instrument_id)]),
    )

    config_node = TradingNodeConfig(
        trader_id="MOMENTUM-001",
        logging=LoggingConfig(log_level="INFO"),
        data_clients={
            IB: InteractiveBrokersDataClientConfig(
                ibg_host=IB_HOST,
                ibg_port=IB_PORT,
                ibg_client_id=DATA_CLIENT_ID,
                handle_revised_bars=False,
                use_regular_trading_hours=False,
                market_data_type=IBMarketDataTypeEnum.DELAYED_FROZEN,
                instrument_provider=inst_provider,
            ),
        },
        exec_clients={
            IB: InteractiveBrokersExecClientConfig(
                ibg_host=IB_HOST,
                ibg_port=IB_PORT,
                ibg_client_id=EXEC_CLIENT_ID,
                account_id=ACCOUNT_ID,
                instrument_provider=inst_provider,
                routing=RoutingConfig(default=True),
            ),
        },
        data_engine=LiveDataEngineConfig(
            time_bars_timestamp_on_close=False,
            validate_data_sequence=True,
        ),
        timeout_connection=90.0,
        timeout_reconciliation=5.0,
        timeout_portfolio=5.0,
        timeout_disconnection=5.0,
        timeout_post_stop=2.0,
    )

    node = TradingNode(config=config_node)

    strat = MomStrategy(
        config=MomConfig(
            instrument_id=instrument_id,
            bar_type=bar_type,
            trade_size=TRADE_SIZE,
            lookback=LOOKBACK,
        ),
    )
    node.trader.add_strategy(strat)

    node.add_data_client_factory(IB, InteractiveBrokersLiveDataClientFactory)
    node.add_exec_client_factory(IB, InteractiveBrokersLiveExecClientFactory)

    node.build()

    if AUTO_STOP_SECS > 0:
        def stop():
            time.sleep(AUTO_STOP_SECS)
            node.stop()
        threading.Thread(target=stop, daemon=True).start()

    try:
        node.run()
    finally:
        node.dispose()


if __name__ == "__main__":
    main()
