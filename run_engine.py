import time

from feeds.ibkr_forecast import start_ibkr_feed, get_ibkr_prices
from feeds.kalshi import get_kalshi_prices

from engine.arb_engine import check_arbitrage


print("STARTING IBKR FEED")
start_ibkr_feed()

print("ARBITRAGE ENGINE RUNNING")


while True:

    ibkr_prices = get_ibkr_prices()
    kalshi_prices = get_kalshi_prices()

    check_arbitrage(ibkr_prices, kalshi_prices)

    time.sleep(2)