from loguru import logger

class MartinPositionManager:
    def __init__(self, factor, max_steps):
        """
        初始化马丁仓位管理器
        :param factor: 因子
        :param max_steps: 最大次数
        """
        self.factor = factor  # 因子
        self.max_steps = max_steps  # 最大次数

        self.cash_distribution = []  # 存储每次分配的资金

        self.count = 0
        self.size = 0
        self.transaction_cost = 0
        self.set_position_count = 0
        self.last_price = 0

    def _calculate_cash_distribution(self, total):
        """
            计算满足条件的一系列数
            :param total: 总和 S
            :param factor: 因子 n
            :param num_elements: 数的个数 k
            :return: 包含 num_elements 个数的列表
        """
        cash_distribution = []
        # remaining_cash = cash  # 剩余总资金
        # for _ in range(self.max_steps):
        #     allocation = remaining_cash / self.factor  # 计算当前分配的资金
        #     remaining_cash = allocation  # 更新剩余总资金
        #     cash_distribution.append(int(allocation))  # 将分配的资金存入列表
        if self.factor == 1:
            cash_distribution = [total / self.max_steps] * self.max_steps
        else:
            n = total * (1 - self.factor) / (1 - self.factor**self.max_steps)
            cash_distribution = [n * self.factor**i for i in range(self.max_steps)]

        self.cash_distribution = sorted(cash_distribution)

    def get_size(self, price):
        if self.last_price != 0:
            if price >= self.last_price:
                return None
        if self.count >= len(self.cash_distribution):
            return None

        size = self.cash_distribution[self.count] / price
        self.count += 1
        self.last_price = price
        return size

    def set_transaction_cost(self, price, size):
        """
        设置价格和持仓
        :return:
        """
        if self.transaction_cost == 0:
            self.transaction_cost = price
        else:
            self.transaction_cost += price
            self.transaction_cost = self.transaction_cost / 2

        self.size += size
        self.set_position_count += 1

    def get_transaction_cost(self):
        """
        获取成本
        :return:
        """
        return self.transaction_cost

    def get_position(self):
        return self.size

    def reset(self, cash):
        if cash <= 0:
            raise Exception("资金使用完毕")
        # 未使用资金加上cash
        if len(self.cash_distribution) > self.count:
            for v in self.cash_distribution[self.count:]:
                cash += v
        logger.info(f"Init Set position cash: {cash} {self.count} {self.set_position_count} {len(self.cash_distribution), self.cash_distribution[self.count:]}")
        self.count = 0
        self.size = 0
        self.transaction_cost = 0
        self.cash_distribution = []
        self.set_position_count = 0
        self.last_price = 0

        self._calculate_cash_distribution(cash)
        logger.info(f"distribution：{self.cash_distribution}")

    def is_completion(self):
        if self.set_position_count == self.count and self.set_position_count != 0:
            return True
        return False

    def stop_loss(self):
        return self.count == self.max_steps and self.set_position_count == self.max_steps


if __name__ == '__main__':
    manager = MartinPositionManager(2, 5)

    manager.reset(100)
    print(manager.cash_distribution)
    for i in range(3):
        size = manager.get_size(11)
        print(size, manager.is_funds_exhausted(), manager.get_transaction_cost())

        manager.set_transaction_cost(2, 3)


    print(manager.count, manager.set_position_count)

    manager.reset(1000)

