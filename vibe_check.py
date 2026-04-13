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
# Using your optimized prematch URL
API_TEMPLATE = "https://ke.sportpesa.com/api/upcoming/games?type=prematch&sportId={sid}&section=upcoming&markets_layout=single&o=leagues&pag_count=1000&pag_min=1"

# --- UTILS ---

def clean_text(text):
    if not text: return ""
    return str(text).replace('"', '').replace("'", "").strip()

def parse_odds(markets):
    h_odd = d_odd = a_odd = 0.0
    if not markets: return h_odd, d_odd, a_odd
    
    main_market = markets[0]
    selections = main_market.get("selections", [])
    
    for s in selections:
        val = float(s.get("odds", 0))
        name = s.get("shortName")
        if name == "1": h_odd = val
        elif name == "X": d_odd = val
        elif name == "2": a_odd = val
    return h_odd, d_odd, a_odd

# --- CORE FETCH (The Playwright Engine) ---

def fetch_all_sports():
    all_games = []
    
    with sync_playwright() as p:
        print("🌐 Launching Chromium...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            # Step 1: Establish a "Human" session
            print("🏠 Touching homepage to clear challenges...")
            page.goto(BASE_URL, wait_until="networkidle")
            time.sleep(random.uniform(5, 8)) 

            for sid in SPORTS:
                url = API_TEMPLATE.format(sid=sid)
                print(f"📡 Fetching Sport ID {sid}...")
                
                page.goto(url)
                # Playwright gets the text directly from the page body
                raw_content = page.locator("body").inner_text()
                
                if "Challenge Validation" in raw_content or len(raw_content) < 2000:
                    print(f"⚠️  Still blocked on Sport {sid} (Length: {len(raw_content)})")
                    continue
                
                data = json.loads(raw_content)
                games = data if isinstance(data, list) else data.get("games", [])
                print(f"✅ Captured {len(games)} games.")
                
                for item in games:
                    record = build_record(item, sid)
                    if record:
                        all_games.append(record)
                
                time.sleep(random.uniform(2, 4))

        except Exception as e:
            print(f"🚨 Browser Error: {e}")
        finally:
            browser.close()
            
    return all_games

def build_record(item, sport_id):
    game_id = str(item.get("id", "")).strip()
    if not game_id: return None

    comp = item.get("competitors", [{}, {}])
    markets = item.get("markets", [])
    h, d, a = parse_odds(markets)

    return {
        "game_id": game_id,
        "sport_id": sport_id,
        "competition": clean_text(item.get("competition", {}).get("name")),
        "home_team": clean_text(comp[0].get("name", "")),
        "away_team": clean_text(comp[1].get("name", "")),
        "match_date": item.get("date"),
        "market_1": h,
        "market_x": d,
        "market_2": a,
        "all_markets": markets,
        "last_updated": datetime.now().isoformat(),
    }

# --- MAIN ---

def vibe_check():
    print("🚀 Lucra Scout — Playwright Edition")
    
    batch = fetch_all_sports()
    
    if batch:
        try:
            # Filter duplicates
            unique_batch = list({v['game_id']: v for v in batch}.values())
            supabase.table("sp_prematch_master").upsert(unique_batch, on_conflict="game_id").execute()
            print(f"\n💎 Successfully synced {len(unique_batch)} unique records.")
            
            # Cleanup
            cutoff = (datetime.now() - timedelta(hours=5)).isoformat()
            supabase.table("sp_prematch_master").delete().lt("match_date", cutoff).execute()
        except Exception as e:
            print(f"\n🚨 Supabase Error: {e}")
    else:
        print("\n🕵️  Scout report: Zero data captured. Firewall 1, Lucra 0.")

if __name__ == "__main__":
    vibe_check()
