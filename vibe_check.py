import os
import cloudscraper # Changed from requests
import time
import random
from supabase import create_client
from datetime import datetime, timedelta

# --- CONFIG ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SPORTS = [1, 2, 4, 5]
BASE_URL = "https://ke.sportpesa.com"
API_URL = f"{BASE_URL}/api/upcoming/games"

# --- UTILS ---

def clean_text(text):
    if not text: return ""
    return str(text).replace('"', '').replace("'", "").strip()

def create_session():
    """
    Creates a cloudscraper session to bypass 'Challenge Validation'.
    It mimics a real browser more effectively than standard requests.
    """
    # This automatically handles the JavaScript challenges
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    return scraper

# --- CORE FETCH ---

def fetch_games(session, sport_id):
    url = f"{API_URL}?sportId={sport_id}"
    
    # These headers help maintain the 'Real Human' vibe
    api_headers = {
        "Accept": "application/json, text/plain, */*",
        "Referer": f"{BASE_URL}/",
        "X-Requested-With": "XMLHttpRequest",
    }

    try:
        # Pacing is key to avoid triggering the firewall again
        time.sleep(random.uniform(3.0, 6.0))
        res = session.get(url, headers=api_headers, timeout=30)

        print(f"\n📡 Sport ID {sport_id} → {url}")
        print(f"   Status: {res.status_code} | Length: {len(res.text)}")

        if res.status_code != 200:
            return []

        # If length is still 1892, we'll see it here
        if "Challenge Validation" in res.text:
            print(f"   🚫 Still hit the challenge page (Length: {len(res.text)})")
            return []

        data = res.json()
        games = data if isinstance(data, list) else data.get("games", [])
        print(f"   ✅ Got {len(games)} games.")
        return games

    except Exception as e:
        print(f"   ⚠️ Error: {e}")
        return []

# --- ODDS PARSING ---

def parse_odds(markets, sport_id):
    h_odd = d_odd = a_odd = 0.0
    if not markets: return h_odd, d_odd, a_odd

    main_market = markets[0]
    m_name = main_market.get("name", "")
    selections = main_market.get("selections", [])

    def get_odd(short_name):
        try:
            return float(next(s["odds"] for s in selections if s.get("shortName") == short_name))
        except (StopIteration, ValueError, KeyError):
            return 0.0

    if m_name == "3 Way":
        h_odd, d_odd, a_odd = get_odd("1"), get_odd("X"), get_odd("2")
    elif "2 Way" in m_name:
        h_odd, a_odd = get_odd("1"), get_odd("2")
    
    return h_odd, d_odd, a_odd

# --- RECORD BUILDER ---

def build_record(item, sport_id):
    game_id = str(item.get("id", "")).strip()
    if not game_id: return None

    competitors = item.get("competitors", [{}, {}])
    home = competitors[0].get("name", "")
    away = competitors[1].get("name", "")
    markets = item.get("markets", [])
    h_odd, d_odd, a_odd = parse_odds(markets, sport_id)

    return {
        "game_id": game_id,
        "sport_id": sport_id,
        "competition": clean_text(item.get("competition", {}).get("name")),
        "home_team": clean_text(home),
        "away_team": clean_text(away),
        "match_date": item.get("date"),
        "market_1": h_odd,
        "market_x": d_odd,
        "market_2": a_odd,
        "all_markets": markets,
        "last_updated": datetime.now().isoformat(),
    }

# --- MAIN ---

def vibe_check():
    print("🚀 Lucra Scout — Bypassing Firewall & Syncing")
    session = create_session()
    batch = []
    seen_ids = set()

    for sport_id in SPORTS:
        games = fetch_games(session, sport_id)
        for item in games:
            record = build_record(item, sport_id)
            if record and record["game_id"] not in seen_ids:
                batch.append(record)
                seen_ids.add(record["game_id"])

    if batch:
        try:
            supabase.table("sp_prematch_master").upsert(batch, on_conflict="game_id").execute()
            print(f"\n✅ Synced {len(batch)} records to Lucra.")
            
            cutoff = (datetime.now() - timedelta(hours=5)).isoformat()
            supabase.table("sp_prematch_master").delete().lt("match_date", cutoff).execute()
        except Exception as e:
            print(f"\n🚨 Supabase error: {e}")
    else:
        print("\n🕵️ Scout report: No data captured.")

if __name__ == "__main__":
    vibe_check()
