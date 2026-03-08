import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from backend.database import get_db
from backend.fetchers.polymarket import fetch_polymarket_markets
from backend.fetchers.predictit import fetch_predictit_markets
from backend.fetchers.kalshi import fetch_kalshi_markets
from backend.fetchers.ibkr import fetch_ibkr_markets
from backend.matcher import find_arbitrage_pairs

logger = logging.getLogger(__name__)

scan_state = {
    "is_scanning": False,
    "progress": 0,
    "phase": "idle",
    "message": "",
    "status": "idle",
    "last_scan_time": None,
    "next_scan_time": None,
    "total_markets": 0,
    "total_opportunities": 0,
    "total_comparisons": 0,
    "completed_comparisons": 0,
    "pairs_found": 0,
    "auto_scan_enabled": False,
}

_scan_signal = asyncio.Event()

_all_markets: List[Dict[str, Any]] = []
_all_opportunities: List[Dict[str, Any]] = []

SCAN_INTERVAL_SECONDS = 300

_matcher_pool = ThreadPoolExecutor(max_workers=1)


def get_scan_state() -> dict:
    return {**scan_state}


def get_cached_markets() -> List[Dict[str, Any]]:
    return _all_markets


def get_cached_opportunities() -> List[Dict[str, Any]]:
    return _all_opportunities


def set_auto_scan(enabled: bool):
    scan_state["auto_scan_enabled"] = enabled
    if enabled:
        _scan_signal.set()
    logger.info(f"Auto-scan {'enabled' if enabled else 'disabled'}")


def get_auto_scan() -> bool:
    return scan_state.get("auto_scan_enabled", False)


_fetch_status: Dict[str, str] = {}


async def _fetch_with_progress(name, fetch_coro_func, results_dict):
    try:
        _fetch_status[name] = "fetching..."
        
        def on_fetch_progress(progress_val, count=None):
            if isinstance(progress_val, int):
                # Page number
                _fetch_status[name] = f"fetching (pg {progress_val}+)"
            else:
                # String status
                _fetch_status[name] = str(progress_val)
        
        # We pass the callback if the fetcher supports it
        import inspect
        sig = inspect.signature(fetch_coro_func)
        if "on_progress" in sig.parameters:
            result = await fetch_coro_func(on_progress=on_fetch_progress)
        else:
            result = await fetch_coro_func()
            
        results_dict[name] = result
        _fetch_status[name] = f"done ({len(result):,})"
        logger.info(f"{name}: fetched {len(result)} markets")
    except Exception as e:
        logger.error(f"{name} fetch error: {e}")
        results_dict[name] = []
        _fetch_status[name] = f"error"


def _update_fetch_progress(total_expected: int):
    parts = []
    # Order them logically
    for name in ["Kalshi", "Polymarket", "PredictIt", "IBKR"]:
        status = _fetch_status.get(name, "waiting")
        parts.append(f"{name}: {status}")
    
    done_count = sum(1 for s in _fetch_status.values() if s.startswith("done") or s == "error")
    
    # Base progress for starting: 3%
    # Fetching phase: up to 45%
    if total_expected > 0:
        # Each done platform adds (42 / count) to the progress
        # Plus a tiny bit for active "fetching" status
        fetching_bonus = sum(0.05 for s in _fetch_status.values() if s.startswith("fetching") or "discovering" in s)
        pct = 3 + int(((done_count + fetching_bonus) / total_expected) * 42)
    else:
        pct = 45
        
    scan_state["progress"] = min(pct, 45)
    scan_state["message"] = " | ".join(parts)


async def _fetch_progress_updater(results_dict, total_expected: int):
    while True:
        _update_fetch_progress(total_expected)
        if len(results_dict) >= total_expected:
            # Final update
            _update_fetch_progress(total_expected)
            break
        await asyncio.sleep(0.5) # Update more frequently


async def run_scan(platforms: Optional[List[str]] = None) -> Dict[str, Any]:
    global _all_markets, _all_opportunities, scan_state

    if scan_state["is_scanning"]:
        return {"status": "already_scanning", "message": "A scan is already in progress"}

    scan_state["is_scanning"] = True
    scan_state["progress"] = 0
    scan_state["phase"] = "Fetching markets"
    scan_state["message"] = "Starting scan..."
    scan_state["status"] = "scanning"
    scan_state["total_comparisons"] = 0
    scan_state["completed_comparisons"] = 0
    scan_state["pairs_found"] = 0
    _fetch_status.clear()

    try:
        scan_state["progress"] = 3
        scan_state["phase"] = "Fetching all platforms"
        scan_state["message"] = "Fetching Kalshi, Polymarket, PredictIt & IBKR in parallel..."

        results: Dict[str, List] = {}
        fetch_tasks = []
        
        # Store as lambda to defer execution (and check signature)
        platform_map = {
            "kalshi": ("Kalshi", lambda on_progress=None: fetch_kalshi_markets(limit=10000, on_progress=on_progress)),
            "polymarket": ("Polymarket", lambda on_progress=None: fetch_polymarket_markets(limit=50000, on_progress=on_progress)),
            "predictit": ("PredictIt", lambda: fetch_predictit_markets()), # PredictIt doesn't have progress yet
            "ibkr": ("IBKR", lambda on_progress=None: fetch_ibkr_markets(on_progress=on_progress)),
        }

        active_platforms = platforms if platforms else ["kalshi", "polymarket", "predictit", "ibkr"]
        active_platforms = [p.lower() for p in active_platforms]
        
        for p_id, (name, coro_func) in platform_map.items():
            is_active = False
            if p_id in active_platforms:
                is_active = True
            else:
                # Check for "IBKR Forecast" match
                for ap in active_platforms:
                    if p_id in ap or ap in p_id:
                        is_active = True
                        break
            
            if is_active:
                fetch_tasks.append(_fetch_with_progress(name, coro_func, results))
            else:
                _fetch_status[name] = "skipped"

        if not fetch_tasks:
            scan_state["status"] = "error"
            scan_state["message"] = "No matching platforms found to scan"
            scan_state["is_scanning"] = False
            return {"status": "error", "message": "No matching platforms found"}

        await asyncio.gather(
            *fetch_tasks,
            _fetch_progress_updater(results, len(fetch_tasks)),
        )

        kalshi_markets = results.get("Kalshi", [])
        poly_markets = results.get("Polymarket", [])
        pi_markets = results.get("PredictIt", [])
        ibkr_markets = results.get("IBKR", [])

        fetch_warnings = []
        if not kalshi_markets:
            fetch_warnings.append("Kalshi returned 0 markets")
        if not poly_markets:
            fetch_warnings.append("Polymarket returned 0 markets")
        if not pi_markets:
            fetch_warnings.append("PredictIt returned 0 markets")
        if not ibkr_markets:
            fetch_warnings.append("IBKR returned 0 markets")
        if fetch_warnings:
            logger.warning(f"Partial fetch: {'; '.join(fetch_warnings)}")

        scan_state["progress"] = 45
        scan_state["message"] = f"Got {len(kalshi_markets)} Kalshi + {len(poly_markets)} Polymarket + {len(pi_markets)} PredictIt + {len(ibkr_markets)} IBKR. Saving to DB..."
        scan_state["phase"] = "Saving markets"

        all_markets = kalshi_markets + poly_markets + pi_markets + ibkr_markets
        _all_markets = all_markets
        scan_state["total_markets"] = len(all_markets)

        db = await get_db()
        try:
            batch_size = 500
            for i in range(0, len(all_markets), batch_size):
                batch = all_markets[i:i+batch_size]
                for m in batch:
                    outcomes_json = json.dumps(m.get("outcomes")) if m.get("outcomes") else None
                    await db.execute(
                        """INSERT OR REPLACE INTO markets 
                           (id, platform, title, category, yes_price, no_price, volume, 
                            last_updated, end_date, market_url, is_binary, outcome_count,
                            contract_label, outcomes_json, fetched_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            m["id"], m["platform"], m["title"], m.get("category", ""),
                            m["yesPrice"], m["noPrice"], m.get("volume", 0),
                            m.get("lastUpdated"), m.get("endDate"), m.get("marketUrl"),
                            1 if m.get("isBinary", True) else 0,
                            m.get("outcomeCount", 2), m.get("contractLabel", ""),
                            outcomes_json, datetime.utcnow().isoformat(),
                        ),
                    )
                await db.commit()
        finally:
            await db.close()

        scan_state["progress"] = 55
        scan_state["phase"] = "Comparing markets"
        scan_state["message"] = "Computing 2-leg arbitrage pairs across all platforms..."

        loop = asyncio.get_event_loop()

        def on_match_progress(completed: int, total: int, pairs_found: int):
            def _update():
                if total > 0:
                    match_pct = completed / total
                    scan_state["progress"] = 55 + int(match_pct * 40)
                scan_state["total_comparisons"] = total
                scan_state["completed_comparisons"] = completed
                scan_state["pairs_found"] = pairs_found
                scan_state["message"] = f"Compared {completed:,}/{total:,} pairs — {pairs_found} matches found"
            loop.call_soon_threadsafe(_update)

        effective_platforms = platforms or ["Kalshi", "Polymarket", "PredictIt", "IBKR"]
        opportunities = await loop.run_in_executor(
            _matcher_pool,
            lambda: find_arbitrage_pairs(all_markets, min_similarity=35.0, enabled_platforms=effective_platforms, on_progress=on_match_progress)
        )
        _all_opportunities = opportunities

        scan_state["progress"] = 95
        scan_state["phase"] = "Saving results"
        scan_state["message"] = f"Found {len(opportunities)} pairs. Saving..."

        db = await get_db()
        try:
            for opp in opportunities[:200]:
                legs_json = json.dumps(opp.get("legs", []))
                await db.execute(
                    """INSERT OR REPLACE INTO matched_pairs
                       (market_a_id, market_b_id, match_score, match_reason,
                        combined_yes_cost, potential_profit, roi, combo_type, leg_count,
                        legs_json, fees, earliest_resolution, scenario)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        opp["marketA"]["id"], opp["marketB"]["id"],
                        opp["matchScore"], opp["matchReason"],
                        opp["combinedYesCost"], opp["potentialProfit"], opp["roi"],
                        opp.get("comboType", "pair"), opp.get("legCount", 2), legs_json,
                        opp.get("fees", 0), opp.get("earliestResolution"),
                        str(opp.get("scenario", "")),
                    ),
                )
            await db.commit()
        finally:
            await db.close()

        scan_state["progress"] = 100
        scan_state["phase"] = "Complete"
        scan_state["status"] = "complete"
        scan_state["total_opportunities"] = len(opportunities)
        scan_state["message"] = f"Scan complete: {len(all_markets)} markets, {len(opportunities)} arbitrage pairs found"
        scan_state["last_scan_time"] = datetime.utcnow().isoformat()
        scan_state["next_scan_time"] = (datetime.utcnow() + timedelta(seconds=SCAN_INTERVAL_SECONDS)).isoformat()

        return {
            "status": "complete",
            "total_markets": len(all_markets),
            "total_opportunities": len(opportunities),
            "markets_by_platform": {
                "Kalshi": len(kalshi_markets),
                "Polymarket": len(poly_markets),
                "PredictIt": len(pi_markets),
                "IBKR": len(ibkr_markets),
            },
        }

    except Exception as e:
        logger.error(f"Scan error: {e}", exc_info=True)
        scan_state["status"] = "error"
        scan_state["message"] = f"Scan error: {str(e)}"
        return {"status": "error", "message": str(e)}

    finally:
        scan_state["is_scanning"] = False


async def auto_scan_loop():
    logger.info("Auto-scan loop worker started")
    while True:
        try:
            # Wait for either the event (manual trigger/toggle) or a timeout (interval)
            if not scan_state.get("auto_scan_enabled", False):
                logger.info("Auto-scan is OFF, waiting for toggle...")
                await _scan_signal.wait()
            
            # Clear it so we don't loop infinitely without waiting
            _scan_signal.clear()
            
            if scan_state.get("auto_scan_enabled", False):
                logger.info("Triggering scan (Auto-scan is ON)")
                result = await run_scan()
                logger.info(f"Scan complete: {result.get('status')} — {result.get('total_markets', 0)} markets found")
            
        except Exception as e:
            logger.error(f"Auto-scan loop error: {e}", exc_info=True)
        
        # Wait for the interval OR a manual trigger via the signal
        try:
            # If auto-scan was just turned off, we'll hit the wait at the top of the loop next
            await asyncio.wait_for(_scan_signal.wait(), timeout=SCAN_INTERVAL_SECONDS)
            logger.info("Auto-scan loop awakened by signal")
        except asyncio.TimeoutError:
            # Timeout is fine, just means we hit the periodic mark
            pass
