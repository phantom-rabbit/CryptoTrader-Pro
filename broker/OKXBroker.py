import sys

import backtrader as bt
import collections
from backtrader.position import Position
from loguru import logger
from .CCXTOrder import CCXTOrder

class Broker(bt.BackBroker):
    params = (
        ('cash', 1000.0),
        ('leverage', 3),
        ('symbol', None),
        ('type', 'SPOT'), # 产品类型 SPOT：币币  SWAP：永续合约
        ('slippage', 0.000),  # 滑点比例%
    )

    SWAP = 'SWAP'
    SPOT = 'SPOT'
    ExecTypes = {bt.Order.Market: 'market',
                   bt.Order.Limit: 'limit',
                   bt.Order.Stop: 'stop',  # stop-loss for kraken, stop for bitmex
                   bt.Order.StopLimit: 'stop limit'}

    OrdTypes = {
        bt.Order.Buy: 'buy',
        bt.Order.Sell: 'sell'
    }


    def __init__(self, store):
        super(Broker, self).__init__()
        self.store = store
        if self._is_swap():
            logger.info(f"Set SWAP {self._symbol()} leverage:{self.p.leverage}")
            self.store.set_leverage(self._symbol(), self.p.leverage)
            self.contract_size = self.get_contract_size()
            logger.info(f"contract_size:{self.contract_size}")

    def _symbol(self):
        if self.p.type == self.SWAP:
            return f"{self.p.symbol}-{self.SWAP}"
        return self.p.symbol

    def _market_id(self):
        if self.p.type == self.SWAP:
            return f"{self.p.symbol.replace('-', '/')}:USDT"
        return self.p.symbol.replace('-', '/')

    def _is_swap(self):
        return self.p.type == self.SWAP

    def _is_spot(self):
        return self.p.type == self.SPOT

    def init(self):
        super(Broker, self).init()
        self.startingcash = self.cash = self.p.cash
        self._value = self.cash
        self.orders = list()
        self.notifs = collections.deque()
        self.positions = collections.defaultdict(Position)

    def get_notification(self):
        try:
            return self.notifs.popleft()
        except IndexError:
            pass

        return None

    def notify(self, order):
        self.notifs.append(order.clone())

    def get_cash(self):
        '''Returns the current cash (alias: ``getcash``)'''
        return self.cash

    getcash = get_cash

    def set_cash(self, cash):
        '''Sets the cash parameter (alias: ``setcash``)'''
        self.startingcash = self.cash = self.p.cash = cash
        self._value = cash

    setcash = set_cash

    def getposition(self, data):
        '''Returns the current position status (a ``Position`` instance) for
        the given ``data``'''
        return self.positions[data]

    def get_value(self, datas=None, mkt=False, lever=False):
        '''Returns the current value of the portfolio'''
        value = self.cash
        for data, position in self.positions.items():
            # 获取当前市场价格
            price = data.close[0]
            value += position.size * price
        return value

    getvalue = get_value

    def _submit(self, data, side, ordtype, size, price):
        ordtyp = self.ExecTypes.get(ordtype)
        if not ordtyp:
            logger.error(f"ordtyp:{ordtyp}")

        side = self.OrdTypes.get(side)
        if not side:
            logger.error(f"side:{side}")

        position = self.getposition(data)
        params = {}
        if self.p.type == self.SWAP:
            params = {
                'tdMode': self.store.ISOLATED, # 逐仓
                'reduceOnly': position.size >= size,
                # slTriggerPx TODO 止损触发价
            }
        result = self.store.create_order(self._symbol(), side, ordtyp, size, price, params=params)
        return result

    def buy(self, owner, data, size, price=None, exectype=bt.Order.Limit, **kwargs):
        side = bt.Order.Buy
        # 滑点
        price = self._calculate_slippage(price, side)
        # 处理限价
        buyLmt, sellLmt = self.get_highest_price_limit(self._symbol())
        if price > buyLmt:
            logger.warning(f"调整买单价格，当前价格{price}, 限价:{buyLmt}")
            price = buyLmt

        # 处理小数位
        size = self.store.handler_precision(self._market_id(), size)
        result = self._submit(data, side, exectype, size, price)
        order = CCXTOrder(owner, data, result, side, size, price, exectype)
        self.orders.append(order)
        return

    def sell(self, owner, data, size, price=None, exectype=bt.Order.Limit, **kwargs):
        side = bt.Order.Sell
        # 滑点
        price = self._calculate_slippage(price, side)

        # 处理限价
        buyLmt, sellLmt = self.get_highest_price_limit(self._symbol())
        if price < sellLmt:
            logger.warning(f"调整买单价格，当前价格{price}, 限价:{sellLmt}")
            price = sellLmt

        # 处理小数位
        size = self.store.handler_precision(self._market_id(), size)
        result = self._submit(data, side, exectype, size, price)
        order = CCXTOrder(owner, data, result, side, size, price, exectype)
        self.orders.append(order)

    def next(self):
        for order in self.orders:
            try:
                ccxt_order = self.store.fetch_order(order.ccxt_order['id'], self._symbol())
                order.update(ccxt_order)
                self._update_position(order)
                self.notify(order)
            except Exception as e:
                logger.error(f"Error fetching order status: {e}")

        # 清理已完成或取消的订单
        self.orders = [order for order in self.orders if order.status in [bt.Order.Submitted, bt.Order.Accepted]]


    def get_highest_price_limit(self, symbol):
        response = self.store.exchange.public_get_public_price_limit({
            'instId': symbol
        })
        return float(response['data'][0]['buyLmt']), float(response['data'][0]['sellLmt'])

    def _update_position(self, order):
        '''Updates the position for the given order'''
        data = order.data
        position = self.positions[data]
        if order.status == bt.Order.Completed:
            if self._is_swap(): #  swap
                margin = (self.contract_size * order.executed.size * order.executed.price) / self.p.leverage
                self.cash -= order.ccxt_order['fee']['cost']
                if order.ccxt_order['reduceOnly']:
                    self.cash += margin
                else:
                    self.cash -= margin

                if order.ordtype == bt.Order.Buy:
                    position.size += order.executed.size
                else:
                    position.size -= order.executed.size

            else:  # spot
                if order.ordtype == bt.Order.Buy:
                    position.size += order.executed.size
                    self.cash -= order.executed.size * order.executed.price
                    # 扣除手续费
                    position.size -= order.executed.comm

                elif order.ordtype == bt.Order.Sell:
                    position.size -= order.executed.size
                    self.cash += order.executed.size * order.executed.price
                    # 扣除手续费
                    self.cash -= order.executed.comm * order.executed.price
        self.positions[data] = position

    def get_contract_size(self):
        """
        获取合约面值
        :return:
        """
        info = self.store.markets.get(self._market_id())
        if not info:
            logger.error(f"{self._market_id()} not in markers")
            sys.exit(1)

        contractSize = info.get('contractSize')
        if not contractSize:
            logger.error(f"{self._market_id()} contractSize not in markers")
            sys.exit(1)

        return contractSize

    def _calculate_open_contracts(self, price):
        """
        计算合约可开仓数量
        :param price:
        :return:
        """
        open_contracts = (self.cash * self.p.leverage) / (self.contract_size * price)
        return open_contracts

    def _calculate_open_spot(self, price):
        """
        计算现货可开仓数量
        :param price:
        :return:
        """
        return (self.cash - 0.1) / price

    def _calculate_open_number(self, price):
        if self._is_swap():
            return self._calculate_open_contracts(price)
        if self._is_spot():
            return self._calculate_open_spot(price)

        return 0

    def _calculate_slippage(self, price, side):
        if self.p.slippage == 0:
            return price

        slippage_amount = price * self.p.slippage
        if side == bt.Order.Buy:
            return price + slippage_amount  #
        else:
            return price - slippage_amount
