import time
from datetime import datetime
import json
from loguru import logger
import threading
import queue
import websocket


class OKXKlineSocket:
    def __init__(self, symbol, interval, sandbox):
        if sandbox:
            self.url = "wss://wspap.okx.com:8443/ws/v5/business"
        else:
            self.url = "wss://ws.okx.com:8443/ws/v5/business"

        self.symbol = symbol
        self.interval = interval
        self.ohlcv = queue.Queue()

        self.ping_interval = 29  # 定时器间隔时间（秒）
        self.ping_message = 'ping'  # ping 消息
        self.timer = None


        self.ws = websocket.WebSocketApp(
            self.url,
            on_message=self._receive_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )

        self.ws.on_open = self._subscribe
        self.ws_thread = threading.Thread(target=self.ws.run_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()

    def _start_timer(self):
        if self.timer:
            self.timer.cancel()  # 取消之前的定时器
        self.timer = threading.Timer(self.ping_interval, self._send_ping)
        self.timer.start()

    def _send_ping(self):
        if self.ws:
            print("Sending ping to server...")
            self.ws.send(str(self.ping_message))
        self._start_timer()  # 重启定时器

    def _on_error(self, ws, error):
        print("Error:", error)

    def _on_close(self, ws, close_status_code, close_msg):
        print("WebSocket closed:", close_status_code, close_msg)
        if self.timer:
            self.timer.cancel()  # WebSocket 关闭时取消定时器

    def _subscribe(self, ws):
        subscribe_message = {
            "op": "subscribe",
            "args": [{
                "channel": "candle" + self.interval,
                "instId": self.symbol
            }]
        }
        ws.send(json.dumps(subscribe_message))
        logger.info(f"Sent: {subscribe_message}")
        self._start_timer()  # 连接建立后启动定时器

    def _receive_message(self, ws, message):
        self._start_timer()  # 重置定时器
        self._handle_message(message)

    def _handle_message(self, message):
        message_data = json.loads(message)
        if "event" in message_data and message_data["event"] == "subscribe":
            logger.info(message_data)
        elif "arg" in message_data and "data" in message_data:
            self._handle_kline_data(message_data)
        else:
            logger.warning(f"Unhandled message: {message_data}")

    def _handle_kline_data(self, message):
        kline_data = message["data"][0]
        # print(kline_data)
        if int(kline_data[-1]) != 0:
            logger.info(f"Kline data: {kline_data}")
            ohlcv = [float(v) for v in kline_data]
            ohlcv[0] = datetime.fromtimestamp(int(ohlcv[0] / 1000))
            self.ohlcv.put(ohlcv)

    def get_ohlcv(self):
        return self.ohlcv.get()



if __name__ == "__main__":
    symbol = "BTC-USDT"
    interval = "1m"
    sandbox = False
    client = OKXKlineSocket(symbol, interval, sandbox)

    while True:
        time.sleep(2)
        ohlcv = client.get_ohlcv()
        print("ohlcv:", ohlcv)
