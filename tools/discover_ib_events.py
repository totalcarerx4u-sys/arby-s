import requests
import json

BASE = "https://forecasttrader.interactivebrokers.com/tws.proxy/public"

url = f"{BASE}/et/eventtrader?id=303"

r = requests.get(url)

print("STATUS:", r.status_code)

data = r.json()

print(json.dumps(data, indent=2))