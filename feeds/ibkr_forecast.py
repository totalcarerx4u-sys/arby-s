import requests
import threading
import time
from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract

from shared.market import Market

URL = "https://forecasttrader.interactivebrokers.com/tws.proxy/public/forecasttrader/contract/market"

params = {
    "underlyingConid": "733131966",
    "exchange": "FORECASTX"
}

data = requests.get(URL, params=params).json()
contracts = data["contracts"]

prices = {}

markets = []

class IB(EWrapper, EClient):

    def __init__(self):
        EClient.__init__(self, self)

    def tickPrice(self, reqId, tickType, price, attrib):
        if price <= 0:
            return

        prices[reqId] = price

        if len(prices) == len(contracts):
            build_markets()

def build_markets():

    global markets
    markets = []

    i = 1

    for c in contracts:

        side = c["side"]
        strike = c["strike_label"]

        price = prices.get(i)

        if price is None:
            continue

        if side == "Y":
            yes = price
            no = 1 - price
        else:
            yes = 1 - price
            no = price

        m = Market(
            event=f"miami_temp_{strike}",
            exchange="IB",
            yes_price=yes,
            no_price=no
        )

        markets.append(m)

        i += 1

    print("\nIB MARKETS")
    for m in markets:
        print(m)

def run_loop():
    app.run()

app = IB()
app.connect("127.0.0.1", 4001, 1)

threading.Thread(target=run_loop, daemon=True).start()

time.sleep(2)

req_id = 1

for c in contracts:

    contract = Contract()
    contract.conId = c["conid"]
    contract.exchange = "FORECASTX"

    app.reqMktData(req_id, contract, "", False, False, [])
    req_id += 1

time.sleep(60)

app.disconnect()