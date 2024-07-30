import websocket
import json
import threading
import logging


class OKXWebSocketClient:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self._connect_ws()

    def _connect_ws(self):
        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        self.ws.on_open = self._on_open
        threading.Thread(target=self.ws.run_forever).start()

    def _on_message(self, ws, message):
        logging.info(f"Received message: {message}")

    def _on_error(self, ws, error):
        logging.error(f"WebSocket error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        logging.info("WebSocket closed")

    def _on_open(self, ws):
        logging.info("WebSocket opened")

    def subscribe_ticker(self, inst_id):
        params = {
            "op": "subscribe",
            "args": [{
                "channel": "tickers",
                "instId": inst_id
            }]
        }
        self.ws.send(json.dumps(params))
