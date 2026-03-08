import asyncio
import httpx
import logging
from typing import List, Dict, Any
from datetime import datetime
from ib_async import IB, Contract, util

logger = logging.getLogger(__name__)

FORECAST_EVENT_URL = "https://forecasttrader.interactivebrokers.com/tws.proxy/public/forecasttrader/event"
FORECAST_MARKET_URL = "https://forecasttrader.interactivebrokers.com/tws.proxy/public/forecasttrader/contract/market"

async def _fetch_events_and_contracts(on_progress: callable = None) -> List[Dict]:
    """Fetches exact YES/NO contracts from the public APIs."""
    contracts_data = []
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Fetch the category tree to discover all active event underlyings
            tree_url = "https://forecasttrader.interactivebrokers.com/tws.proxy/public/forecasttrader/category/tree"
            headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
            
            logger.info("Fetching ForecastEx category tree...")
            tree_resp = await client.get(tree_url, headers=headers)
            tree_resp.raise_for_status()
            
            categories = tree_resp.json().get("categories", {})
            
            # Extract all underlying conids from all categories
            known_underlyings = []
            for cat_id, cat_data in categories.items():
                for market in cat_data.get("markets", []):
                    if "conid" in market:
                        known_underlyings.append((market["conid"], market["name"]))
                        
            logger.info(f"Discovered {len(known_underlyings)} total event underlyings in category tree.")
            
            # For each underlying, fetch its specific YES/NO contracts
            logger.info(f"Fetching specific contracts for {len(known_underlyings)} events...")
            
            for i, (underlying_conid, event_name) in enumerate(known_underlyings):
                if on_progress:
                    on_progress(f"discovering {i+1}/{len(known_underlyings)}")
                try:
                    params = {
                        "underlyingConid": str(underlying_conid),
                        "exchange": "FORECASTX"
                    }
                    market_resp = await client.get(FORECAST_MARKET_URL, params=params, headers=headers)
                    market_resp.raise_for_status()
                    market_data = market_resp.json()
                    
                    market_contracts = market_data.get("contracts", [])
                    
                    for mc in market_contracts:
                        mc["event_name"] = event_name
                        mc["underlyingConid"] = underlying_conid
                        contracts_data.append(mc)
                        
                except Exception as e:
                    logger.debug(f"Failed to fetch market data for event {underlying_conid}: {e}")
                    
    except Exception as e:
        logger.error(f"Error fetching from ForecastEx API: {e}")
        
    return contracts_data


async def fetch_ibkr_markets(on_progress: callable = None) -> List[Dict[str, Any]]:
    """
    Combines REST discovery with TWS live pricing to generate the standard markets feed.
    """
    logger.info("Discovering IBKR ForecastEx markets via REST...")
    raw_contracts = await _fetch_events_and_contracts(on_progress=on_progress)
    
    if not raw_contracts:
        logger.warning("No IBKR contracts found from public API.")
        return []

    logger.info(f"Discovered {len(raw_contracts)} IBKR contracts. Connecting to TWS/Gateway...")
    if on_progress:
        on_progress(f"connecting to TWS...")
    
    ib = IB()
    markets = []
    
    try:
        # Connect to localhost TWS or Gateway. 
        # Typically 4001/4002 for Gateway, 7496/7497 for TWS.
        # We use a random client ID to avoid conflicts.
        logger.info("Attempting to connect to IBKR TWS/Gateway (127.0.0.1:4001)...")
        await asyncio.wait_for(ib.connectAsync('127.0.0.1', 4001, clientId=101), timeout=15.0)
        
        # We need to map the raw contracts back to our uniform Market structure
        # A single 'Market' in our system represents a Yes/No pair.
        # ForecastEx has a contract for YES and a contract for NO.
        # Sometimes one conid represents YES and another represents NO. Let's see how to bundle them.
        
        # Group YES and NO contracts by their strike
        grouped_markets = {}
        
        for rc in raw_contracts:
            strike = rc.get("strike_label", rc.get("strike", "0"))
            side = rc.get("side", "Y")  # 'Y' or 'N'
            conid = rc.get("conid")
            event_name = rc.get("event_name", "Unknown Event")
            
            group_key = f"{event_name}_{strike}"
            
            if group_key not in grouped_markets:
                grouped_markets[group_key] = {
                    "event_name": event_name,
                    "strike": strike,
                    "yes_conid": None,
                    "no_conid": None,
                    "description": rc.get("description", event_name)
                }
                
            if side == "Y":
                grouped_markets[group_key]["yes_conid"] = conid
            elif side == "N":
                grouped_markets[group_key]["no_conid"] = conid

        # Prepare IB Contracts
        ib_contracts = []
        conid_to_market_key = {}
        
        for k, v in grouped_markets.items():
            if v["yes_conid"]:
                c = Contract(conId=int(v["yes_conid"]), exchange="FORECASTX")
                ib_contracts.append(c)
                conid_to_market_key[v["yes_conid"]] = (k, "Y")
            if v["no_conid"]:
                c = Contract(conId=int(v["no_conid"]), exchange="FORECASTX")
                ib_contracts.append(c)
                conid_to_market_key[v["no_conid"]] = (k, "N")

        # Qualify contracts
        qualified = await ib.qualifyContractsAsync(*ib_contracts)
        
        # Request live market data snapshots
        # Use reqTickers to get snapshot data, it completes quickly
        tickers = await ib.reqTickersAsync(*qualified)
        
        # Extract prices
        group_prices = {}
        for k in grouped_markets:
            group_prices[k] = {"yes_price": 0.5, "no_price": 0.5}

        for t in tickers:
            conid = t.contract.conId
            if conid in conid_to_market_key:
                k, side = conid_to_market_key[conid]
                
                # Best approximation of current price
                # We use the midpoint of bid/ask, fallback to last, fallback to 0.5
                bid = t.bid if t.bid and t.bid > 0 else None
                ask = t.ask if t.ask and t.ask > 0 else None
                
                price = None
                if bid is not None and ask is not None:
                    # ForecastEx prices usually quoted between 0 and 1, or 0 and 100
                    # Assuming 0.0 to 1.0 based on ibkr_forecast.py reference code
                    price = (bid + ask) / 2.0
                elif t.last and t.last > 0:
                    price = t.last
                elif bid is not None:
                    price = bid
                elif ask is not None:
                    price = ask
                
                if price is not None:
                    # In ibkr_forecast.py: "if side == 'Y' yes = price / no = 1-price"
                    # We'll use the precise fetched prices if both available
                    if side == "Y":
                        group_prices[k]["yes_price"] = price
                    else:
                        group_prices[k]["no_price"] = price
        
        # Build final uniform market list
        for k, gm in grouped_markets.items():
            prices = group_prices[k]
            
            # If we couldn't get real market data, skip
            if prices["yes_price"] == 0.5 and prices["no_price"] == 0.5:
                continue

            # In some FORECASTX setups, the YES contract price implies the NO price implicitly (1 - YES),
            # but usually there are explicit Yes/No contracts with their own order books.
            yes_p = prices["yes_price"]
            no_p = prices["no_price"]
            
            title = f"{gm['event_name']} - {gm['strike']}" if str(gm["strike"]) != "0" else gm["event_name"]
            
            market = {
                "id": f"ibkr_{gm['yes_conid']}_{gm['no_conid']}",
                "platform": "IBKR",
                "title": title,
                "category": gm['event_name'],
                "yesPrice": round(yes_p, 4),
                "noPrice": round(no_p, 4),
                "volume": 0,  # IB ticker volume can be added if mapped (t.volume)
                "lastUpdated": datetime.utcnow().isoformat(),
                "endDate": None, # Usually embedded in contract details, left null for now
                "marketUrl": "https://forecasttrader.interactivebrokers.com", 
                "isBinary": True,
                "outcomeCount": 2,
                "contractLabel": "Yes",
                "outcomes": None,
            }
            markets.append(market)

    except Exception as e:
        logger.error(f"IBKR TWS fetch error: {e}")
    finally:
        ib.disconnect()

    logger.info(f"Successfully constructed {len(markets)} IBKR markets.")
    return markets

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = asyncio.run(fetch_ibkr_markets())
    for m in res[:5]:
        print(m)
