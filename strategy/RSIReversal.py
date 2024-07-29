import backtrader as bt
from loguru import logger
import numpy as np


class RSIReversal(bt.Strategy):
    params = (
        ('boll_period', 60),  # 布林带的周期长度
        ('boll_dev', 3.0),  # 布林带的标准差倍数
        ('rsi_period', 50),  # 短期RSI周期
        ('rsi_buy_signal', 40),  # 中期RSI周期
        ('rsi_downward_period', 8),  # 连续下降或横盘周期
        ('stop_loss', 0.1),  # 止损百分比
    )

    def __init__(self):
        self.dataclose = self.datas[0].close
        self.rsi = bt.indicators.RSI(self.data.close, period=self.params.rsi_period)
        self.boll = bt.indicators.BollingerBands(self.data.close, period=self.params.boll_period,
                                                 devfactor=self.params.boll_dev)

        self.buy_signal = False
        self.sell_signal = False

        self.commission = 0
        self.WinningTrades = 0
        self.LosingTrades = 0
        self.TotalProfit = 0
        self.TotalLoss = 0
        self.StopLoss = 0

        self._op = bt.Order.Buy
        self._buy_price = 0
        self._open_order = None

    def start(self):
        logger.info("策略开始运行, 等待行情数据...")

    def stop(self):
        report = self.generate_combinations_report()
        logger.info(self.params.__dict__)
        logger.info(report)

    def notify_order(self, order):
        order_info = (
            f"订单参考: {order.ref}, 类型: {'买单' if order.isbuy() else '卖单'}, 状态: {order.getstatusname()}, "
            f"价格: {order.executed.price}, 数量: {order.executed.size}, 成交均价: {order.executed.price}, 佣金: {order.executed.comm}"
        )
        logger.info(order_info)

        if order.status == bt.Order.Completed:
            self._open_order = False
            if order.isbuy():
                self._op = bt.Order.Sell
                self._buy_price = order.executed.price
                # logger.debug(f"买入订单. 价格:{order.executed.price} 数量:{order.executed.size:.8f}")
            else:
                # logger.debug(
                #     f"卖出订单. {self.datas[0].datetime.datetime(0)} 买入价:{self._buy_price} 成交价格:{order.executed.price} 成交量:{order.executed.size:.8f} 盈亏:{():.4f}")
                profit = (order.executed.price - self._buy_price) * (order.executed.size * -1)
                if profit < 0:
                    self.LosingTrades += 1
                    self.TotalLoss -= profit
                else:
                    self.WinningTrades += 1
                    self.TotalProfit += profit

                logger.info(f"{self.LosingTrades} {self.TotalLoss} {self.WinningTrades} {self.TotalProfit}")
                self._op = bt.Order.Buy
                self._buy_price = 0

            # 获取当前头寸
            position = self.getposition(self.data).size
            cash = self.broker.getcash()
            commission = order.executed.comm
            # if commission < 0:
            #     commission = commission * -1
            self.commission += commission

            logger.info(f"position:{position:.8f} cach:{cash:.4f} commission:{commission}")

    def next(self):
        if len(self.datas[0]) < max(self.params.boll_period, self.params.rsi_period):
            logger.debug(f"time:{self.datas[0].datetime.datetime(0)} close price:{self.datas[0].close[0]}")
            return
        logger.debug(f"[{self.data.datetime.datetime(0)}], "
                     f"收盘价: {self.data.close[0]}, "
                     f"最高价: {self.data.high[0]}, "
                     f"最低价: {self.data.low[0]}, "
                     f"成交量: {self.data.volume[0]:.8f}, "
                     f"RSI值: {self.rsi[0]}, "
                     f"布林带上轨: {self.boll.lines.top[0]}, "
                     f"中轨: {self.boll.lines.mid[0]}, "
                     f"下轨: {self.boll.lines.bot[0]}")
        self.risk_management()
        self.handle_oscillating_market()

    def _sumit_buy_order(self, price, size, exectype, **kwargs):
        order = self.buy(price=price, size=size, exectype=exectype, **kwargs)
        self._open_order = True
        return order

    def _sumit_sell_order(self, price, size, exectype, **kwargs):
        order = self.sell(price=price, size=size, exectype=exectype, **kwargs)
        self._open_order = True
        return order

    def generate_combinations_report(self):
        avg_loss = 0
        avg_profit = 0
        winningtrades = 0
        rate = 0
        startingcash = self.broker.startingcash
        if self.WinningTrades != 0:
            avg_profit = self.TotalProfit / self.WinningTrades
        if self.LosingTrades != 0:
            avg_loss = self.TotalLoss / self.LosingTrades
        if self.WinningTrades != 0:
            winningtrades = f"{(self.WinningTrades / (self.WinningTrades + self.LosingTrades) * 100):.2f}%"

        if avg_loss != 0:
            rate = (avg_profit / avg_loss)
        net_profit = self.TotalProfit - self.TotalLoss - self.commission
        return_rate = 0
        if net_profit !=0:
            return_rate = net_profit / startingcash * 100
        return {
            "手续费": float(f"{self.commission:.4f}"),
            "胜率": winningtrades,
            "获胜": self.WinningTrades,
            "失败": self.LosingTrades,
            "盈亏比": float(f"{rate:.2f}"),
            "利润(平均)": float(f"{avg_profit:.2f}"),
            "亏损(平均)": float(f"{avg_loss:.2f}"),
            "总利润": float(f"{self.TotalProfit:.2f}"),
            "总亏损": float(f"{self.TotalLoss:.2f}"),
            "净利润": float(f"{net_profit:.2f}"),
            "收益率": f"{return_rate:.4f}%",
            "止损次数": self.StopLoss,
        }

    def handle_oscillating_market(self):
        if self._open_order:  # 有未完成订单
            return
        current_close = self.data.close[0]
        current_time = self.datas[0].datetime.datetime(0)
        recent_rsi_list = np.array([self.rsi[-i] for i in range(1, self.p.rsi_downward_period)])

        # close_values = np.array([self.data.close[-i] for i in range(3)])
        # close_trend = np.all(np.diff(close_values) >= 0)

        # 计算差分数组，并判断是否所有差值都大于0（即上升趋势）
        is_rsi_downward = np.all(np.diff(recent_rsi_list) <= 0)
        # 成交量
        volume = np.array([self.data.volume[-i] for i in range(1, 6)])

        logger.debug(f"RSI:{recent_rsi_list} 是否连续下降趋势:{is_rsi_downward}")
        # logger.debug(f"收盘价:{close_values} 连续上升:{close_trend}")

        if self._op == bt.Order.Buy:
            if self.rsi[0] < self.p.rsi_buy_signal:  # rsi 阈值
                if is_rsi_downward:  # rsi连续下降
                    if current_close > self.data.close[-1]:  # rsi 底部价格和rsi背离
                        cash = self.broker.getcash() - 0.1   # 避免计算精度问题导致溢价
                        size = cash / current_close
                        order = self._sumit_buy_order(current_close, size, bt.Order.Limit)
                        if order:
                            self.buy_signal = False
                            logger.info(
                                f"买入订单.{current_time} 价格:{current_close} 数量:{size:.8f} cash:{cash} 成交量:{volume}")
                            return

            if self.rsi[0] < 10: # 超卖，反转
                cash = self.broker.getcash() - 0.1  # 避免计算精度问题导致溢价
                size = cash / current_close
                order = self._sumit_buy_order(current_close, size, bt.Order.Limit)
                if order:
                    self.buy_signal = False
                    logger.info(
                        f"买入订单.{current_time} 价格:{current_close} 数量:{size:.8f} cash:{cash} 成交量:{volume}")
                    return

        if self._op == bt.Order.Sell:
            if current_close >= self.boll.lines.mid[0]:
                if current_close < self.boll.lines.top[0] and not is_rsi_downward and self.rsi[0] < 80:
                    return
                size = self.getposition(self.data).size
                order = self._sumit_sell_order(current_close, size, bt.Order.Limit)
                if order:
                    self.sell_signal = False
                    self._open_order = True
                    logger.info(
                        f"卖出订单. {current_time} 买单价格:{self._buy_price} 当前价格:{current_close} 数量:{size:.8f} 浮盈:{((current_close * size) - (self._buy_price * size)):.4f} rsi:{self.rsi[0]}")
                    return

    def risk_management(self):
        """风险管理"""
        if not self._open_order and self._op == bt.Order.Sell:
            current_price = self.data.close[0]
            current_time = self.datas[0].datetime.datetime(0)
            if current_price < (self._buy_price * (1 - self.p.stop_loss)):
                size = self.getposition(self.data).size
                order = self._sumit_sell_order(current_price, size, bt.Order.Limit)
                if order:
                    self.sell_signal = False
                    self._open_order = True
                    logger.info(
                        f"止损. {current_time} 买单价格:{self._buy_price} 当前价格:{current_price} 数量:{size:.8f} 浮盈:{((current_price * size) - (self._buy_price * size)):.4f}")
                    self.StopLoss += 1
