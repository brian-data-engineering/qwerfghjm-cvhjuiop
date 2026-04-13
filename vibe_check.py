import os
import requests
import json
from supabase import create_client
from datetime import datetime, timedelta

# --- CONFIGURATION ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()

# Initialize Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def clean_text(text):
    if not text: return ""
    # Removing quotes for Lucra code compatibility and database integrity
    return str(text).replace('"', '').replace("'", "").strip()

def fetch_data(sport_id):
    """
    Scouts the Sportpesa upcoming API for a specific sport.
    Uses enhanced headers to bypass common bot-detection filters.
    """
    url = f"https://ke.sportpesa.com/api/upcoming/games?sportId={sport_id}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://ke.sportpesa.com/",
        "Origin": "https://ke.sportpesa.com",
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        res = requests.get(url, headers=headers, timeout=25)
        
        if res.status_code != 200:
            print(f"❌ Scout Blocked: Status {res.status_code} for Sport {sport_id}")
            return []
            
        data = res.json()
        
        # Handle cases where the API wraps the list in a 'data' or 'games' key
        if isinstance(data, dict):
            return data.get('games', data.get('data', []))
        return data if isinstance(data, list) else []
        
    except Exception as e:
        print(f"⚠️ Scout Error for Sport {sport_id}: {e}")
        return []

def vibe_check():
    # The Core Four: Soccer, Basketball, Hockey, Tennis
    SPORTS_LIST = [1, 2, 4, 5]
    batch_to_upsert = []
    synced_ids = []

    print(f"📡 Lucra Scout: Scanning for Heroes...")

    for sport_id in SPORTS_LIST:
        data = fetch_data(sport_id)
        if not data:
            continue

        for item in data:
            game_id = str(item.get('id'))
            synced_ids.append(game_id)

            # 1. ODDS PARSING (Safe extraction of 1x2 markets)
            markets = item.get('markets', [])
            h_odd, d_odd, a_odd = 0.0, 0.0, 0.0
            
            if markets and len(markets) > 0:
                selections = markets[0].get('selections', [])
                try:
                    # Using next() with a default of 0 to avoid StopIteration errors
                    h_odd = float(next((s['odds'] for s in selections if s['shortName'] == '1'), 0))
                    d_odd = float(next((s['odds'] for s in selections if s['shortName'] == 'X'), 0))
                    a_odd = float(next((s['odds'] for s in selections if s['shortName'] == '2'), 0))
                except (ValueError, TypeError):
                    pass

            # 2. CONSTRUCT OBJECT
            batch_to_upsert.append({
                "game_id": game_id,
                "sport_id": item.get('sport', {}).get('id'),
                "competition": clean_text(item.get('competition', {}).get('name')),
                "home_team": clean_text(item.get('competitors', [{}])[0].get('name')),
                "away_team": clean_text(item.get('competitors', [{}, {}])[1].get('name')),
                "match_date": item.get('date'),
                "market_1": h_odd,
                "market_x": d_odd,
                "market_2": a_odd,
                "all_markets": markets, # Storing full JSON for the 'Deep Odds' scraper later
                "last_updated": datetime.now().isoformat()
            })

    # 3. UPSERT TO SUPABASE
    if batch_to_upsert:
        try:
            supabase.table("sp_prematch_master").upsert(
                batch_to_upsert, 
                on_conflict="game_id"
            ).execute()
            print(f"✅ Success! {len(batch_to_upsert)} heroes synced.")

            # 4. CLEANUP (Keep the DB light by removing games that started > 4 hours ago)
            cutoff = (datetime.now() - timedelta(hours=4)).isoformat()
            supabase.table("sp_prematch_master").delete().lt("match_date", cutoff).execute()
            print(f"🧹 Lucra Cleanup: Old heroes cleared.")
            
        except Exception as e:
            print(f"🚨 Database Error: {e}")
    else:
        print("⚠️ No fresh vibes found. Checking endpoints or headers may be required.")

if __name__ == "__main__":
    vibe_check()
