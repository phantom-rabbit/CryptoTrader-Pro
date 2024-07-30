import time
import base64
import hmac
import hashlib
import requests
import json


def _get_timestamp():
    return str(time.time())


class OKXAPI:
    def __init__(self, params):
        self.api_key = params.get('api_key')
        self.api_secret = params.get('api_secret')
        self.passphrase = params.get('passphrase')
        self.is_demo = params.get('is_demo', True)
        self.base_url = 'https://www.okx.com'
        if self.is_demo:
            self.base_url = 'https://www.okx.com/demo'

    def _sign_message(self, timestamp, method, endpoint, body):
        message = timestamp + method + endpoint + body
        hmac_key = base64.b64decode(self.api_secret)
        signature = base64.b64encode(hmac.new(hmac_key, message.encode(), hashlib.sha256).digest()).decode()
        return signature

    def _send_request(self, method, endpoint, body):
        timestamp = _get_timestamp()
        body_str = json.dumps(body)
        signature = self._sign_message(timestamp, method, endpoint, body_str)

        headers = {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }

        url = self.base_url + endpoint
        response = requests.request(method, url, headers=headers, data=body_str)
        return response.json()
