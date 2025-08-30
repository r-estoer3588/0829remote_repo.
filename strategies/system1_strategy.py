"""System1 strategy wrapper class using shared core functions.

This class integrates with YAML-driven settings for backtest parameters
and relies on StrategyBase to inject risk/system-specific config.  As an
extension example, Alpaca 発注処理も組み込み、バックテストと実売双方に
対応できるようにする。
"""

from __future__ import annotations

import os
import pandas as pd

from .base_strategy import StrategyBase
from system.core import (
    prepare_data_vectorized_system1,
    generate_roc200_ranking_system1,
    get_total_days_system1,
)
from common.backtest_utils import simulate_trades_with_risk

try:  # pragma: no cover - alpaca-py が未導入でもインポート失敗を防ぐ
    from alpaca.trading.client import TradingClient
    from alpaca.trading.enums import OrderSide, OrderClass, TimeInForce
    from alpaca.trading.requests import (
        MarketOrderRequest,
        LimitOrderRequest,
        TakeProfitRequest,
        StopLossRequest,
        TrailingStopOrderRequest,
    )
    from alpaca.trading.stream import TradingStream
except Exception:  # pragma: no cover
    TradingClient = None  # type: ignore
    MarketOrderRequest = LimitOrderRequest = TakeProfitRequest = StopLossRequest = TrailingStopOrderRequest = None  # type: ignore
    OrderSide = OrderClass = TimeInForce = None  # type: ignore
    TradingStream = None  # type: ignore


class System1Strategy(StrategyBase):
    SYSTEM_NAME = "system1"

    def prepare_data(self, raw_data_dict, **kwargs):
        progress_callback = kwargs.pop("progress_callback", None)
        log_callback = kwargs.pop("log_callback", None)
        skip_callback = kwargs.pop("skip_callback", None)

        return prepare_data_vectorized_system1(
            raw_data_dict,
            progress_callback=progress_callback,
            log_callback=log_callback,
            skip_callback=skip_callback,
            **kwargs,
        )

    def generate_candidates(self, prepared_dict, market_df=None, **kwargs):
        # Pull top-N from YAML backtest config
        try:
            from config.settings import get_settings
            top_n = get_settings(create_dirs=False).backtest.top_n_rank
        except Exception:
            top_n = 10
        if market_df is None:
            market_df = prepared_dict.get("SPY")
            if market_df is None:
                raise ValueError("SPY data not found in prepared_dict.")
        return generate_roc200_ranking_system1(prepared_dict, market_df, top_n=top_n, **kwargs)

    def run_backtest(
        self, prepared_dict, candidates_by_date, capital, on_progress=None, on_log=None
    ) -> pd.DataFrame:
        trades_df, logs_df = simulate_trades_with_risk(
            candidates_by_date,
            prepared_dict,
            capital,
            self,
            on_progress=on_progress,
            on_log=on_log,
        )

        # Optional: stream capital trajectory to UI via on_log
        if on_log and not logs_df.empty:
            for _, row in logs_df.iterrows():
                on_log(
                    f"{row['date'].date()} | Capital: {row['capital']:.2f} USD | Active: {row['active_count']}"
                )

        return trades_df

    def get_total_days(self, data_dict: dict) -> int:
        return get_total_days_system1(data_dict)

    # ===============================
    # リアルタイム売買向け Alpaca 連携
    # ===============================
    def init_trading_client(self, *, paper: bool = True) -> TradingClient:
        """.env から API キーを読み込み TradingClient を生成する。

        Parameters
        ----------
        paper: bool, default True
            Paper Trading (デフォルト) か本番かを指定。
        """
        if TradingClient is None:
            raise RuntimeError(
                "alpaca-py がインストールされていません。requirements に追加してください。"
            )
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        if not api_key or not secret_key:
            raise RuntimeError("ALPACA_API_KEY/ALPACA_SECRET_KEY が .env に設定されていません。")
        return TradingClient(api_key, secret_key, paper=paper)

    def submit_order(
        self,
        client: TradingClient,
        symbol: str,
        qty: int,
        side: str = "buy",
        order_type: str = "market",
        *,
        limit_price: float | None = None,
        stop_price: float | None = None,
        take_profit: float | None = None,
        stop_loss: float | None = None,
        trail_percent: float | None = None,
        log_callback=None,
    ):
        """Alpaca へ注文を送信するユーティリティ。

        Parameters
        ----------
        client: TradingClient
            `init_trading_client` で生成したクライアント。
        symbol: str
            ティッカーシンボル。
        qty: int
            株数。
        side: str
            "buy" or "sell"。
        order_type: str
            "market", "limit", "oco", "trailing_stop" のいずれか。
        limit_price, stop_price, take_profit, stop_loss, trail_percent
            注文種別に応じて利用される価格・比率。
        log_callback: callable, optional
            ログ出力コールバック。
        """
        if TradingClient is None:
            raise RuntimeError("alpaca-py がインストールされていません。")

        side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        tif = TimeInForce.GTC

        if order_type == "market":
            req = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side_enum,
                time_in_force=tif,
            )
        elif order_type == "limit":
            if limit_price is None:
                raise ValueError("limit_price が必要です。")
            req = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side_enum,
                limit_price=limit_price,
                time_in_force=tif,
            )
        elif order_type == "oco":
            if take_profit is None or stop_loss is None:
                raise ValueError("take_profit と stop_loss が必要です。")
            req = LimitOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side_enum,
                time_in_force=tif,
                order_class=OrderClass.OCO,
                take_profit=TakeProfitRequest(limit_price=take_profit),
                stop_loss=StopLossRequest(stop_price=stop_loss),
            )
        elif order_type == "trailing_stop":
            if trail_percent is None and stop_price is None:
                raise ValueError("trail_percent か trail_price のいずれかが必要です。")
            req = TrailingStopOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side_enum,
                time_in_force=tif,
                trail_percent=trail_percent,
                trail_price=stop_price,
            )
        else:
            raise ValueError(f"未知の order_type: {order_type}")

        order = client.submit_order(order_data=req)
        if log_callback:
            log_callback(
                f"Submitted {order_type} order {order.id} {symbol} qty={qty} side={side_enum.name}"
            )
        return order

    def log_orders_positions(self, client: TradingClient, log_callback=None):
        """現在の注文・ポジションを取得してログ出力する。"""
        orders = client.get_orders(status="all")
        positions = client.get_all_positions()
        if log_callback:
            for o in orders:
                log_callback(
                    f"Order {o.id} {o.symbol} {o.side} {o.status} filled={o.filled_qty}"
                )
            for p in positions:
                log_callback(
                    f"Position {p.symbol} qty={p.qty} avg_entry={p.avg_entry_price}"
                )
        return orders, positions

    def subscribe_order_updates(
        self, client: TradingClient, log_callback=None
    ) -> TradingStream:
        """注文更新の WebSocket を購読し、更新時にログ出力する。"""
        if TradingStream is None:
            raise RuntimeError("alpaca-py がインストールされていません。")

        stream = TradingStream(
            client.api_key, client.secret_key, paper=client.paper
        )

        @stream.on_order_update
        async def _(data):  # noqa: ANN001 - Alpaca SDK 固有シグネチャ
            if log_callback:
                log_callback(
                    f"WS update {data.event} id={data.order.id} status={data.order.status}"
                )

        stream.run()  # 実行はブロッキング。適宜スレッド化/async 対応が必要。
        return stream

