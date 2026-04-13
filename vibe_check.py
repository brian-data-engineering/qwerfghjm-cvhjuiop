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
    session = requests.Session()
    
    # Reverted to your specified endpoint
    url = f"https://ke.sportpesa.com/api/upcoming/games?sportId={sport_id}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://ke.sportpesa.com/",
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        # Pacing requests to avoid 400 errors
        time.sleep(random.uniform(1.5, 3.0))
        
        res = session.get(url, headers=headers, timeout=30)
        
        # Clean logging output
        print(f"📡 Scout hitting: {url}")
        print(f"📊 Status: {res.status_code}")
        
        if res.status_code == 200:
            content = res.text.strip()
            if not content:
                print("🕵️ Result: Empty response body.")
                return []
            
            data = res.json()
            return data if isinstance(data, list) else data.get('games', [])
            
    except Exception as e:
        # Separate error message from the URL to avoid formatting issues
        print(f"⚠️ Error encountered for ID {sport_id}")
        print(f"📝 {str(e)}")
            
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
            
            cutoff = (datetime.now() - timedelta(hours=5)).isoformat()
            supabase.table("sp_prematch_master").delete().lt("match_date", cutoff).execute()
            print("🧹 Cleanup: Old match data pruned.")
        except Exception as e:
            print(f"🚨 Supabase Error: {e}")
    else:
        print("🕵️ Scout report: No heroes found. Verify endpoint availability.")

if __name__ == "__main__":
    vibe_check()
