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
    
    # Switched to the mobile API which is often more lenient with data-center IPs
    url = f"https://m.ke.sportpesa.com/api/upcoming/games?sportId={sport_id}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://m.ke.sportpesa.com/",
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        # Increased delay range to mimic human browsing and prevent rate-limiting (400 errors)
        time.sleep(random.uniform(2.5, 4.5))
        
        res = session.get(url, headers=headers, timeout=30)
        
        # Clean logging: No extra characters or confusing splits
        print(f"📡 Scout Request -> Sport ID: {sport_id} | Status: {res.status_code}")
        
        if res.status_code == 200:
            if not res.text.strip():
                print(f"🕵️ Empty response body for Sport {sport_id} (Possible IP Block)")
                return []
            
            data = res.json()
            # The mobile API structure usually mirrors the web API
            games = data if isinstance(data, list) else data.get('games', data.get('data', []))
            return games
        else:
            print(f"⚠️ Unexpected Response: {res.status_code}")
            
    except Exception as e:
        # Log error clearly without appending it directly to the URL string
        print(f"🚨 Scout Error on Sport {sport_id}")
        print(f"📝 Details: {str(e)}")
            
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
            
            # Extract 1X2 odds
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
            
            # Prune data older than 5 hours
            cutoff = (datetime.now() - timedelta(hours=5)).isoformat()
            supabase.table("sp_prematch_master").delete().lt("match_date", cutoff).execute()
            print("🧹 Cleanup: Old match data pruned.")
        except Exception as e:
            print(f"🚨 Supabase Error: {e}")
    else:
        print("🕵️ Scout report: All attempts returned empty or failed. Verify if GitHub Runners are blocked.")

if __name__ == "__main__":
    vibe_check()
