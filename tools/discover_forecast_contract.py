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
        print("FOUND FORECAST CONTRACT")
        print("Symbol:", c.symbol)
        print("SecType:", c.secType)
        print("Exchange:", c.exchange)
        print("Currency:", c.currency)
        print("ConId:", c.conId)
        print("----------------------")

def run_loop():
    app.run()

app = IB()
app.connect("127.0.0.1", 4001, 1)

# start socket listener
thread = threading.Thread(target=run_loop, daemon=True)
thread.start()

time.sleep(2)

contract = Contract()
contract.symbol = "HORC"
contract.secType = "FUT"
contract.exchange = "FORECASTX"
contract.currency = "USD"

app.reqContractDetails(1, contract)

# keep script alive so response can arrive
time.sleep(15)

app.disconnect()