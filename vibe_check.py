import os
import requests
import time
import random
from supabase import create_client
from datetime import datetime, timedelta

# --- CONFIG ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def clean_text(text):
    if not text: return ""
    return str(text).replace('"', '').replace("'", "").strip()

def fetch_heroes(sport_id):
    # Using a session to manage cookies like a real browser
    session = requests.Session()
    
    endpoints = [
        f"https://ke.sportpesa.com/api/upcoming/games?sportId={sport_id}",
        f"https://ke.sportpesa.com/api/highlights/games?sportId={sport_id}"
    ]
    
    # Mobile headers are less likely to be blocked by aggressive WAFs
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-GB,en;q=0.9",
        "Referer": "https://ke.sportpesa.com/",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }

    for url in endpoints:
        try:
            # Random delay to mimic human behavior
            time.sleep(random.uniform(1.0, 2.0))
            
            res = session.get(url, headers=headers, timeout=30)
            
            # Print status for transparency
            endpoint_name = url.split('/')[-1].split('?')[0]
            print(f"📡 Scout hitting {endpoint_name} (ID: {sport_id}) | Status: {res.status_code}")
            
            # Check if body is empty before parsing JSON (prevents char 0 error)
            if not res.text.strip():
                print(f"🕵️ Shadow Blocked: {endpoint_name} returned an empty response.")
                continue

            data = res.json()
            games = data if isinstance(data, list) else data.get('games', data.get('data', []))
            if games:
                return games
                
        except Exception as e:
            print(f"⚠️ Scout Error on {url}: {e}")
            
    return []

def vibe_check():
    SPORTS = [1, 2, 4, 5]
    batch = []
    seen_ids = set()

    print("📡 Lucra Scout: Syncing heroes from Sportpesa...")

    for sid in SPORTS:
        data = fetch_heroes(sid)
        if not data: continue

        for item in data:
            game_id = str(item.get('id'))
            if game_id in seen_ids: continue
            
            markets = item.get('markets', [])
            h_odd, d_odd, a_odd = 0.0, 0.0, 0.0
            
            # Specific 3-Way market extraction
            if markets and markets[0].get('name') == '3 Way':
                selections = markets[0].get('selections', [])
                try:
                    h_odd = float(next((s['odds'] for s in selections if s['shortName'] == '1'), 0))
                    d_odd = float(next((s['odds'] for s in selections if s['shortName'] == 'X'), 0))
                    a_odd = float(next((s['odds'] for s in selections if s['shortName'] == '2'), 0))
                except (StopIteration, ValueError): pass

            batch.append({
                "game_id": game_id,
                "sport_id": sid,
                "competition": clean_text(item.get('competition', {}).get('name')),
                "home_team": clean_text(item.get('competitors', [{}])[0].get('name')),
                "away_team": clean_text(item.get('competitors', [{}, {}])[1].get('name')),
                "match_date": item.get('date'),
                "market_1": h_odd,
                "market_x": d_odd,
                "market_2": a_odd,
                "all_markets": markets,
                "last_updated": datetime.now().isoformat()
            })
            seen_ids.add(game_id)

    if batch:
        try:
            supabase.table("sp_prematch_master").upsert(batch, on_conflict="game_id").execute()
            print(f"✅ Success! {len(batch)} heroes are now in Lucra.")
            
            # Maintain db health
            cutoff = (datetime.now() - timedelta(hours=5)).isoformat()
            supabase.table("sp_prematch_master").delete().lt("match_date", cutoff).execute()
            print("🧹 Cleanup: Old match data pruned.")
        except Exception as e:
            print(f"🚨 Supabase Error: {e}")
    else:
        print("🕵️ Scout report: All endpoints returned empty. GitHub IP is likely blacklisted.")

if __name__ == "__main__":
    vibe_check()
