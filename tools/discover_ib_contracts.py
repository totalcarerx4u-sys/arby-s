from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import time

class IB(EWrapper, EClient):

    def __init__(self):
        EClient.__init__(self, self)

    def contractDetails(self, reqId, contractDetails):
        c = contractDetails.contract
        print("FOUND CONTRACT")
        print("Symbol:", c.symbol)
        print("SecType:", c.secType)
        print("Exchange:", c.exchange)
        print("Currency:", c.currency)
        print("ConId:", c.conId)
        print("---------------------")

def run_loop():
    app.run()

app = IB()
app.connect("127.0.0.1", 4001, clientId=1)

thread = threading.Thread(target=run_loop, daemon=True)
thread.start()

time.sleep(2)

contract = Contract()
contract.symbol = "AAPL"
contract.secType = "STK"
contract.exchange = "SMART"
contract.currency = "USD"

app.reqContractDetails(1, contract)

time.sleep(10)

app.disconnect()