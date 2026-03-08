from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import time

class IBApp(EWrapper, EClient):

    def __init__(self):
        EClient.__init__(self, self)

    def tickPrice(self, reqId, tickType, price, attrib):
        print("Price:", price)

def run_loop():
    app.run()

app = IBApp()
app.connect("127.0.0.1", 4001, 1)

thread = threading.Thread(target=run_loop, daemon=True)
thread.start()

time.sleep(1)

contract = Contract()
contract.conId = 762089343
contract.exchange = "FORECASTX"

app.reqMarketDataType(3)
app.reqMktData(1, contract, "", False, False, [])

time.sleep(30)
app.disconnect()