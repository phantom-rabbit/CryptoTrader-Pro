import sys

import backtrader as bt
from loguru import logger


class SWAPStrategy(bt.Strategy):
    params = (
        ('rsi_period', 5),  # RSI周期
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI(self.data.close, period=self.params.rsi_period)
        self.rsi_high = bt.indicators.RSI(self.data.high, period=self.params.rsi_period)
        self.ema = bt.indicators.ExponentialMovingAverage(self.data, period=self.params.rsi_period)

    def can_sell(self):
        if 73 < self.rsi[0] <= self.rsi[-1]:
            return True
        if self.rsi[0] > 85:
            return True
        return False

    def can_buy(self):
        if 23 > self.rsi[0] >= self.rsi[-1]:
            return True
        if self.rsi[0] < 15:
            return True
        return False
    # ADX 连续下跌 反转

    def next(self):
        current_close = self.data.close[0]
        current_time = self.datas[0].datetime.datetime(0)
        # position = self.broker.getposition(self.data)
        # getcash = self.broker.getcash()
        data = self.datas[0]
        logger.info(
            f"{data.datetime.datetime()}, Open: {data.open[0]}, High: {data.high[0]}, Low: {data.low[0]}, Close: {data.close[0]}, Volume: {data.volume[0]:.2f}",
        )
        logger.info(f"{current_time} {current_close} RSI:{self.rsi[0]:2f} EMA:{self.ema[0]}")

        return
        if len(self.broker.orders) != 0:
            return

        if position.size > 0:  # 平多单
            if self.can_sell():
                self.sell(price=current_close, size=position.size, exectype=bt.Order.Limit)
        elif position.size == 0:  # 开仓
            if self.can_sell():
                size = self.broker.calculate_open_number(current_close, bt.Order.Sell)
                self.sell(price=current_close, size=size, exectype=bt.Order.Limit)
            elif self.can_buy():
                size = self.broker.calculate_open_number(current_close, bt.Order.Buy)
                self.buy(price=current_close, size=size, exectype=bt.Order.Limit)
        elif position.size < 0:  # 平仓空单
            if self.can_buy():
                size = position.size * -1
                self.buy(price=current_close, size=size, exectype=bt.Order.Limit)
