from ibapi.client import EClient
from ibapi.wrapper import EWrapper
import threading
import time

class TestApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)

    def nextValidId(self, orderId):
        print("CONNECTED TO IB GATEWAY")
        print("Next order id:", orderId)

app = TestApp()

app.connect("127.0.0.1", 4001, clientId=1)

thread = threading.Thread(target=app.run, daemon=True)
thread.start()

time.sleep(5)

app.disconnect()