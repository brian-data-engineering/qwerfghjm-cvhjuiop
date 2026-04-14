import os
import json
import time
import random
from playwright.sync_api import sync_playwright
from supabase import create_client
from datetime import datetime, timedelta

# --- CONFIG ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SPORTS = [1, 2, 4, 5]
BASE_URL = "https://ke.sportpesa.com"

# Endpoint 1: To get the list of games
LIST_API = "https://ke.sportpesa.com/api/upcoming/games?type=prematch&sportId={sid}"
# Endpoint 2: Your deep market discovery
DEEP_API = "https://ke.sportpesa.com/api/games/markets?games={gids}&markets=all"

# --- UTILS ---

def clean_text(text):
    if not text: return ""
    return str(text).replace('"', '').replace("'", "").strip()

def extract_main_odds(markets):
    """Helper to pull 1X2 odds from the first market for the table columns."""
    h = d = a = 0.0
    if not markets: return h, d, a
    
    # Usually the first market is '3 Way'
    selections = markets[0].get("selections", [])
    for s in selections:
        val = float(s.get("odds", 0))
        sn = s.get("shortName")
        if sn == "1": h = val
        elif sn == "X": d = val
        elif sn == "2": a = val
    return h, d, a

# --- CORE ENGINE ---

def sync_lucra():
    all_records = {}

    with sync_playwright() as p:
        print("🌐 Launching Unified Browser Engine...")
        browser = p.chromium.launch(headless=True)
        # Use a single context to keep session cookies alive
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            # 1. Handshake: Clear challenges
            print("🏠 Touching homepage to establish session...")
            page.goto(BASE_URL, wait_until="networkidle")
            time.sleep(6) 

            # 2. Scout Game IDs
            for sid in SPORTS:
                print(f"📡 Scouting Sport ID {sid}...")
                page.goto(LIST_API.format(sid=sid))
                
                raw_list = page.locator("body").inner_text()
                if "Challenge Validation" in raw_list:
                    print(f"⚠️  Scout blocked on Sport {sid}")
                    continue

                data = json.loads(raw_list)
                games = data if isinstance(data, list) else data.get("games", [])
                
                for g in games:
                    gid = str(g.get("id"))
                    all_records[gid] = {
                        "game_id": gid,
                        "sport_id": sid,
                        "competition": clean_text(g.get("competition", {}).get("name")),
                        "home_team": clean_text(g.get("competitors", [{}])[0].get("name", "")),
                        "away_team": clean_text(g.get("competitors", [{}, {}])[1].get("name", "")),
                        "match_date": g.get("date"),
                        "market_1": 0.0, "market_x": 0.0, "market_2": 0.0,
                        "all_markets": [], # Placeholder for Step 3
                        "last_updated": datetime.now().isoformat()
                    }
                time.sleep(random.uniform(1, 2))

            # 3. Batch Deep Dive (The All Markets Fetch)
            gids = list(all_records.keys())
            batch_size = 40 
            
            for i in range(0, len(gids), batch_size):
                chunk = gids[i : i + batch_size]
                batch_str = ",".join(chunk)
                print(f"💎 Deep Syncing batch {i//batch_size + 1} ({len(chunk)} games)...")
                
                page.goto(DEEP_API.format(gids=batch_str))
                raw_deep = page.locator("body").inner_text()
                
                if "Challenge Validation" in raw_deep:
                    print("🚨 Firewall trigger on deep fetch. Waiting...")
                    time.sleep(10)
                    continue

                deep_json = json.loads(raw_deep)
                for game_data in deep_json:
                    gid = str(game_data.get("id"))
                    if gid in all_records:
                        markets = game_data.get("markets", [])
                        all_records[gid]["all_markets"] = markets
                        
                        # Update the main 1X2 columns from the deep data
                        h, d, a = extract_main_odds(markets)
                        all_records[gid]["market_1"] = h
                        all_records[gid]["market_x"] = d
                        all_records[gid]["market_2"] = a

                time.sleep(random.uniform(2, 4))

        except Exception as e:
            print(f"🚨 Engine Error: {e}")
        finally:
            browser.close()

    return list(all_records.values())

# --- RUN ---

def vibe_check():
    print("🚀 Lucra Deep Scout — Starting All-in-One Browser Sync")
    
    final_batch = sync_lucra()
    
    if final_batch:
        try:
            # Perform a single massive upsert
            supabase.table("sp_prematch_master").upsert(final_batch, on_conflict="game_id").execute()
            print(f"\n✅ Mission Success: {len(final_batch)} games with Deep Odds synced.")
            
            # Maintenance: Prune matches older than 5 hours
            cutoff = (datetime.now() - timedelta(hours=5)).isoformat()
            supabase.table("sp_prematch_master").delete().lt("match_date", cutoff).execute()
        except Exception as e:
            print(f"🚨 Supabase DB Error: {e}")
    else:
        print("\n🕵️  No data found. Check your session warmup or firewall status.")

if __name__ == "__main__":
    vibe_check()
