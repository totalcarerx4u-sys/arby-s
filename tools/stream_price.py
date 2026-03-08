from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import time

class IB(EWrapper, EClient):

    def __init__(self):
        EClient.__init__(self, self)

    def tickPrice(self, reqId, tickType, price, attrib):
        print("Price update:", price)

def run_loop():
    app.run()

app = IB()
app.connect("127.0.0.1", 4001, clientId=1)

thread = threading.Thread(target=run_loop, daemon=True)
thread.start()

time.sleep(2)

# THIS LINE ENABLES DELAYED DATA
app.reqMarketDataType(3)

contract = Contract()
contract.symbol = "AAPL"
contract.secType = "STK"
contract.exchange = "SMART"
contract.currency = "USD"

app.reqMktData(1, contract, "", False, False, [])

time.sleep(20)

app.disconnect()