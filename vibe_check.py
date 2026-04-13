import os
import requests
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
    # Try multiple endpoints as fallback to bypass empty responses
    endpoints = [
        f"https://ke.sportpesa.com/api/upcoming/games?sportId={sport_id}",
        f"https://ke.sportpesa.com/api/highlights/games?sportId={sport_id}"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://ke.sportpesa.com/",
        "X-Requested-With": "XMLHttpRequest"
    }

    for url in endpoints:
        try:
            res = requests.get(url, headers=headers, timeout=25)
            # Log status for GitHub Actions debugging
            print(f"📡 Scout hitting {url.split('/')[-1]} | Status: {res.status_code}")
            
            if res.status_code == 200:
                data = res.json()
                # Handle both list and dict-wrapped responses
                games = data if isinstance(data, list) else data.get('games', data.get('data', []))
                if games:
                    return games
        except Exception as e:
            print(f"⚠️ Scout Error: {e}")
            
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
            
            # Extract Odds (Safely navigating the '3 Way' market)
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
        supabase.table("sp_prematch_master").upsert(batch, on_conflict="game_id").execute()
        print(f"✅ Success! {len(batch)} heroes are now in Lucra.")
        
        # Cleanup: Remove heroes that are 5 hours old
        cutoff = (datetime.now() - timedelta(hours=5)).isoformat()
        try:
            supabase.table("sp_prematch_master").delete().lt("match_date", cutoff).execute()
            print("🧹 Cleanup: Old match data pruned.")
        except Exception as e:
            print(f"⚠️ Cleanup note: {e}")
    else:
        print("🕵️ Scout report: No data found across all endpoints. Possible IP block.")

if __name__ == "__main__":
    vibe_check()
