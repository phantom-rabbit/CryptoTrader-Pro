import backtrader as bt
import numpy as np

from .MartinPositionManager import MartinPositionManager
from loguru import logger


class MartingaleLongStrategy(bt.Strategy):
    params = (
        ('max_steps', 5),  # 资金分成的份数
        ('factor', 2),  # 马丁因子
        ('take_profit', 0.08),  # 止盈百分比
        ('stop_loss', 0.2),  # 止损百分比
        ('rsi_period', 60),  # RSI周期
        ('rsi_downward', 6),  # RSI周期
    )

    def __init__(self):
        self.rsi_close = bt.indicators.RSI(self.data.close, period=self.params.rsi_period)
        self.martingale_position = MartinPositionManager(self.p.factor, self.p.max_steps)
        cash = self.broker.getcash()
        logger.info(f"Set init cash:{cash}")
        self.martingale_position.reset(cash)

        self.commission = 0
        self.count = 0

    def _signal(self):
        current_time = self.datas[0].datetime.datetime(0)
        rsis = np.array([round(self.rsi_close[-i], 2) for i in range(1, self.p.rsi_downward)])

        # 连续下降，反转趋势
        if self.rsi_close[0] < 30:
            if np.all(np.diff(rsis) >= 0) and round(self.rsi_close[0], 2) > rsis[0]:
                logger.info(f"[信号] LONG {current_time} rsi_close:{self.rsi_close[0]:.2f} {rsis}")
                return bt.SIGNAL_LONG

    def next(self):
        price = self.data.close[0]
        current_time = self.datas[0].datetime.datetime(0)
        cost = self.martingale_position.get_transaction_cost()
        # 止损
        if self.martingale_position.stop_loss():  # 全部成交
            if price <= cost * (1 - self.p.stop_loss):
                size = self.martingale_position.get_position()
                logger.warning(f"[止损] {current_time}当前价:{price} 成本价:{cost} 数量:{size}")
                order = self.sell(price=price, size=size, exectype=bt.Order.Limit)
                return

        # 止盈
        if self.martingale_position.is_completion():
            if cost != 0:
                # logger.info(f"{price} {cost}")
                if price >= cost * (1 + self.p.take_profit):
                    size = self.martingale_position.get_position()
                    logger.info(f"[止盈] {current_time}当前价:{price} 成本价:{cost} 数量:{size}")
                    order = self.sell(price=price, size=size, exectype=bt.Order.Limit)
                    return

        # 开仓
        signal = self._signal()
        if signal != bt.SIGNAL_LONG:
            return
        size = self.martingale_position.get_size(price)
        if size:
            logger.info(f"[开仓] {current_time}价格:{price} 数量:{size}")
            order = self.buy(price=price, size=size, exectype=bt.Order.Limit)
            return

    def notify_order(self, order):
        current_time = self.datas[0].datetime.datetime(0)
        order_info = (
            f"{current_time} 订单: {order.ref}, 类型: {'买单' if order.isbuy() else '卖单'}, 状态: {order.getstatusname()}, "
            f"价格: {order.price}, 数量: {order.executed.size}, 成交均价: {order.executed.price}, 手续费: {order.executed.comm}"
        )
        logger.info(order_info)

        if order.status in [order.Completed]:
            price = order.executed.price
            size = order.executed.size
            commission = order.executed.comm
            self.commission += commission
            if order.isbuy():
                logger.info(f"set_transaction_cost:{price} {size}")
                self.martingale_position.set_transaction_cost(price, size)
            else:
                cash = price * (size * -1) - commission
                logger.info(f"cash:{cash} {price} {size}")
                self.martingale_position.reset(cash)

            self.count += 1

    def stop(self):
        logger.info(f"手续费:{self.commission} 交易完成次数:{self.count}")


if __name__ == '__main__':
    cerebro = bt.Cerebro()
    logger.add("aa.log", level='DEBUG')
    # 加载数据
    from datetime import datetime
    import pandas as pd

    path = "../tests/FILUSDT_1m_2024-05-01_2024-05-30_okx_testnet.csv"
    path = "../tests/FILUSDT_1m_2024-05-01_2024-05-30_okx_testnet.csv"
    df = pd.read_csv(path, index_col='datetime', parse_dates=True)

    data = bt.feeds.PandasData(dataname=df)
    cerebro.adddata(data)
    # 添加策略
    cerebro.addstrategy(MartingaleLongStrategy,
                        take_profit=0.1, factor=4)

    # 设置初始资金
    cerebro.broker.set_cash(1000)

    # 运行策略
    print('Starting Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.run()
    print('Ending Portfolio Value: %.2f' % cerebro.broker.getvalue())
    cerebro.plot()
