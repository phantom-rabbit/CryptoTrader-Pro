import backtrader as bt


class CCXTOrder(bt.OrderBase):
    def __init__(self, owner, data, ccxt_order, side, size, price, exectype):
        self.owner = owner
        self.data = data
        self.ccxt_order = ccxt_order
        self.executed_fills = []
        self.ordtype = side
        self.size = size
        self.price = price
        self.exectype = exectype

        super(CCXTOrder, self).__init__()

    def update(self, ccxt_order):
        self.ccxt_order = ccxt_order
        self.executed.size = ccxt_order['filled']
        self.executed.price = (ccxt_order['average'] if 'average' in ccxt_order else ccxt_order['price'])
        self.executed.comm = ccxt_order['fee']['cost']
        if ccxt_order['status'] == 'closed':
            self.status = bt.Order.Completed
        elif ccxt_order['status'] == 'canceled':
            self.status = bt.Order.Canceled
        elif ccxt_order['status'] == 'open':
            self.status = bt.Order.Accepted
        else:
            self.status = bt.Order.Rejected
