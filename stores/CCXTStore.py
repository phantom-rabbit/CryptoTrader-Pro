import json
import sys
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN

import backtrader as bt
import pandas as pd
import ccxt
from loguru import logger


def truncate_to_decimal_places(number, decimal_places):
    # 确保 decimal_places 是整数
    decimal_places = int(decimal_places)

    # 将数字转换为 Decimal 类型
    decimal_number = Decimal(str(number))

    # 构建截断的格式字符串，例如：'1.00000000' 表示保留 8 位小数
    format_string = '1.' + '0' * decimal_places

    # 使用 quantize 进行截断，不进行四舍五入
    truncated_number = decimal_number.quantize(Decimal(format_string), rounding=ROUND_DOWN)

    # 去除多余的零
    return truncated_number.normalize()


class CCXTStore(bt.DataBase):
    params = (
        ('api_key', None),
        ('api_secret', None),
        ('password', None),
        ('exchange_name', 'okx'),
        ('sandbox', False),  # 是否为模拟盘交易
        ('symbol', None),
        ('interval', '1m'),
    )

    # 保证金模式：isolated：逐仓 ；cross：全仓
    ISOLATED = 'isolated'
    CROSS = 'cross'

    def __init__(self):
        super(CCXTStore, self).__init__()
        exchange_class = getattr(ccxt, self.p.exchange_name)
        self.exchange = exchange_class({
            'apiKey': self.p.api_key,
            'secret': self.p.api_secret,
            'password': self.p.password,
            'enableRateLimit': True,
        })

        logger.info(f"Connecting to {self.p.exchange_name}...")

        if self.p.sandbox:
            logger.info("Switching to sandbox mode")
            self.exchange.set_sandbox_mode(True)

        try:
            self.markets = self.exchange.load_markets()

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            sys.exit(1)

        self.last_ts = 0
        self.ohlcv = []
        self.kline_symbol = self.p.symbol
        self.kline_interval = self.p.interval
        logger.info(f"Set kline {self.kline_symbol} {self.kline_interval}")

    def set_Kline_symbol(self, symbol):
        self.kline_symbol = self.p.symbol = symbol

    def set_leverage(self, symbol, leverage, mgnMode='isolated'):
        """
        :param symbol:
        :param leverage:
        :param mgnMode:  # 'isolated'（逐仓模式）
        :return:
        """
        leverage_data = {
            'instId': symbol,
            'lever': leverage,
            'mgnMode': mgnMode,
        }

        # 设置杠杆倍数
        try:
            self.exchange.private_post_account_set_leverage(leverage_data)
        except Exception as e:
            logger.error(e)
            sys.exit(1)

    def create_order(self, symbol, side, order_type, amount, price=None, params={}):
        logger.debug(f"[{self.p.exchange_name}] New order: {symbol}, {side}, {order_type}, amount:{amount}, price:{price}, {params}")
        try:
            order = self.exchange.create_order(symbol, order_type, side, amount, price, params)
            logger.debug(f"[{self.p.exchange_name}] Order created: {json.dumps(order)}")
            return order
        except Exception as e:
            logger.error(f"[{self.p.exchange_name}] Failed to create order: {e}")
            raise e

    def fetch_order(self, order_id, symbol):
        try:
            order = self.exchange.fetch_order(order_id, symbol)
            logger.info(f"Order details: {json.dumps(order)}")
            return order
        except Exception as e:
            logger.error(f"Failed to fetch order: {e}")

    def cancel_order(self, order_id, symbol):
        try:
            result = self.exchange.cancel_order(order_id, symbol)
            logger.info(f"Order cancelled: {result}")
            return result
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")

    def handler_precision(self, symbol, price, value):
        price_precision = int(abs(Decimal(str(self.markets[symbol]['precision']['price'])).as_tuple().exponent))
        price = truncate_to_decimal_places(price, price_precision)

        amount_precision = int(abs(Decimal(str(self.markets[symbol]['precision']['amount'])).as_tuple().exponent))
        value = truncate_to_decimal_places(value, amount_precision)
        return price, value

    def fetch_positions(self, symbol):
        positions = self.exchange.fetch_positions(symbols=[symbol])
        return positions[0]['info']

    def haslivedata(self):
        if len(self.ohlcv) != 0:
            return True
        else:
            return False

    def islive(self):
        return True

    def _load(self):
        try:
            if not self.ohlcv:
                while not self.ohlcv:
                    time.sleep(2)
                    to_ = self.fetch_time()
                    if 60 - datetime.fromtimestamp(to_ / 1000).second > 10:
                        continue
                    from_ = to_ - self._interval_to_milliseconds(self.kline_interval)

                    if self.is_same_minute(to_, self.last_ts):
                        continue
                    self.fetch_data(from_, to_)

            if self.ohlcv:
                ohlc = self.ohlcv.pop(0)
                ohlc[0] = bt.date2num(ohlc[0])
                self.lines.datetime[0] = ohlc[0]
                self.lines.open[0] = ohlc[1]
                self.lines.high[0] = ohlc[2]
                self.lines.low[0] = ohlc[3]
                self.lines.close[0] = ohlc[4]
                self.lines.volume[0] = ohlc[5]

                return True
            else:
                return False
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            return False

    def is_same_minute(self, timestamp1, timestamp2):
        dt1 = datetime.fromtimestamp(timestamp1 / 1000, tz=timezone.utc) + timedelta(hours=8)
        dt2 = datetime.fromtimestamp(timestamp2 / 1000, tz=timezone.utc) + timedelta(hours=8)
        return dt1.strftime('%Y-%m-%d %H:%M') == dt2.strftime('%Y-%m-%d %H:%M')

    def _interval_to_milliseconds(self, interval):
        unit = interval[-1]
        amount = int(interval[:-1])
        if unit == 'm':
            return amount * 60 * 1000
        elif unit == 'h':
            return amount * 3600 * 1000
        elif unit == 'd':
            return amount * 86400 * 1000
        else:
            raise ValueError(f"Invalid interval: {interval}")

    def pre_fetch_data(self, limit):
        """预加载数据"""
        logger.info(f"pre fetch data {limit}")
        to_ = int(datetime.now(timezone.utc).timestamp()) * 1000
        from_ = to_ - self._interval_to_milliseconds(self.kline_interval) * limit
        self.fetch_data(from_, to_, limit=100)

    def fetch_data(self, from_timestamp, to_timestamp, limit=10):
        try:
            current_timestamp = from_timestamp
            while current_timestamp < to_timestamp:
                ohlcvs = self.exchange.fetch_ohlcv(self.kline_symbol, self.kline_interval, since=current_timestamp,
                                                   limit=limit)
                if ohlcvs:
                    back_one = ohlcvs[-1][0]
                    for ohlcv in ohlcvs:
                        if ohlcv[-1] == 0:
                            continue
                        if ohlcv[0] > self.last_ts:
                            index_timestamp = ohlcv[0]
                            ohlcv[0] = datetime.fromtimestamp(ohlcv[0] / 1000)
                            self.last_ts = index_timestamp
                            self.ohlcv.append(ohlcv)
                            logger.debug(
                                f"Fetched data {self.kline_symbol} point: {datetime.fromtimestamp(index_timestamp / 1000).strftime('%Y-%m-%d %H:%M:%S')} limit {len(ohlcvs)}")
                    current_timestamp = back_one + 1  # 更新当前时间戳为最后一个数据点的时间戳+1
                else:
                    break
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            raise e

    def fetch_time(self):
        server_time = self.exchange.fetch_time()
        return server_time

    def save_to_csv(self, fromdate, todate, path):
        if fromdate and todate:
            from_timestamp = int(fromdate.timestamp() * 1000)
            to_timestamp = int(todate.timestamp() * 1000)
            if to_timestamp < from_timestamp:
                logger.warning("开始时间小于结束时间")
                sys.exit(1)

            self.fetch_data(from_timestamp, to_timestamp, limit=100)

        else:
            logger.error("时间区间不能为空")
            sys.exit(1)

        columns = ['datetime', 'open', 'high', 'low', 'close', 'volume']
        df = pd.DataFrame(self.ohlcv, columns=columns)
        df['openinterest'] = 0  # 新增一列，并且数据都为0
        df = df[columns + ['openinterest']]
        path = f"{path}_{self.p.exchange_name}_{'testnet' if self.p.sandbox else 'mainnet'}.csv"
        df.to_csv(path, index=False)
        logger.info(f"save to {path}")


class MyStrategy(bt.SignalStrategy):
    def __init__(self):
        self.flag = False
        self.AA = False

    def next(self):
        getcash = self.broker.getcash()
        value = self.broker.get_value()
        position = self.broker.getposition(self.data)
        print(f"持仓大小: {position.size:4f} 现金:{getcash:.4f}")
        # print(getcash, value, self.data.datetime.datetime(0), self.data.close[0])
        if self.AA:
            return
        if not self.flag:
            price = self.data.close[0]
            # self.buy(self, self.data, size=1, price=self.data.close[0], exectype=bt.Order.Limit)
            contracts_size = self.broker._calculate_open_number(price)
            order = self.buy(price=price, size=contracts_size, exectype=bt.Order.Limit)
            self.flag = True
            return
        if self.flag:
            price = self.data.close[0]
            order = self.sell(price=price, size=position.size, exectype=bt.Order.Limit)
            self.AA = True

    def notify_order(self, order):
        order_info = (
            f"订单参考: {order.ref}, 类型: {'买单' if order.isbuy() else '卖单'}, 状态: {order.getstatusname()}, "
            f"价格: {order.executed.price}, 数量: {order.executed.size}, 成交均价: {order.executed.price}, 手续费: {order.executed.comm}"
        )

        logger.info(order_info)


if __name__ == '__main__':
    symbol = 'FIL-USDT'
    params = {
        'api_key': "b2151fec-0aaa-4571-a3b9-8ab4ce276e3a",
        'api_secret': "7D5D310BFB49EEA5E017EBB9F258F027",
        'password': "Lol@123456",
        'exchange_name': "okx",
        'sandbox': True,
        'symbol': symbol,
        'interval': '1m'
    }

    ccxt_store = CCXTStore(**params)

    # ccxt_store.set_leverage(symbol, 3)
    # # #
    # order = ccxt_store.create_order(symbol, 'BUY', 'limit', 10, 4.36,     params={
    #     'tdMode': 'isolated',  # 逐仓模式
    # })
    # print(order)

    # start = pd.to_datetime('2023-01-01')
    # end = pd.to_datetime('2023-01-02')
    # ccxt_store.save_to_csv(start, end, '')
    cerebro = bt.Cerebro()
    cerebro.addstrategy(MyStrategy)
    cerebro.adddata(ccxt_store)
    cerebro.addstore(ccxt_store)
    from broker.OKXBroker import Broker

    cerebro.setbroker(Broker(
        store=ccxt_store,
        cash=10,
        symbol=symbol,
        type='SPOT',
        slippage=0.003))
    cerebro.run()
