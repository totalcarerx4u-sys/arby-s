import requests

URL = "https://api.elections.kalshi.com/trade-api/v2/markets"


def get_kalshi_prices():

    prices = {
        "DEMOCRAT": None,
        "REPUBLICAN": None
    }

    response = requests.get(URL)
    data = response.json()

    markets = data.get("markets", [])

    for m in markets:

        title = m.get("title", "")

        yes_bid = m.get("yes_bid")

        if yes_bid is None:
            continue

        price = yes_bid / 100

        title_lower = title.lower()

        if "democrat" in title_lower:
            prices["DEMOCRAT"] = price

        if "republican" in title_lower:
            prices["REPUBLICAN"] = price

    return prices