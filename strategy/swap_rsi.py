import sys

import backtrader as bt
from loguru import logger


class SWAPStrategy(bt.Strategy):
    params = (
        ('rsi_period', 5),  # RSI周期
        ('adx_period', 5),  # ADX周期
    )

    def __init__(self):
        self.rsi = bt.indicators.RSI(self.data.close, period=self.params.rsi_period)
        self.adx = bt.indicators.AverageDirectionalMovementIndex(
            period=self.params.adx_period,
            movav=bt.indicators.SimpleMovingAverage  # 使用参数指定的移动平均线类型
        )
        self.ema = bt.indicators.ExponentialMovingAverage(self.data, period=self.params.rsi_period)

    def can_sell(self):
        if 73 < self.rsi[0] <= self.rsi[-1]:
            return True
        if self.rsi[0] > 85:
            return True
        return False

    def can_buy(self):
        if 27 > self.rsi[0] >= self.rsi[-1]:
            return True
        if self.rsi[0] < 13:
            return True
        return False
    # ADX 连续下跌 反转

    def next(self):
        current_close = self.data.close[0]
        current_time = self.datas[0].datetime.datetime(0)
        position = self.broker.getposition(self.data)
        getcash = self.broker.getcash()
        logger.info(f"{current_time} {current_close} RSI:{self.rsi[0]:2f} ADX:{self.adx[0]:4f} EMA:{self.ema[0]}")
        if len(self.broker.orders) != 0:
            return
        if position.size != 0:
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
