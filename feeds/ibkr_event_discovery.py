import requests

BASE = "https://forecasttrader.interactivebrokers.com/tws.proxy/public/forecasttrader"


def discover_events():

    url = f"{BASE}/event"

    r = requests.get(url)

    if r.status_code != 200:
        print("Failed to load events:", r.status_code)
        return []

    data = r.json()

    events = []

    for e in data:

        events.append({
            "name": e["name"],
            "conid": e["underlyingConid"]
        })

    return events