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
    url = f"https://ke.sportpesa.com/api/upcoming/games?sportId={sport_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://ke.sportpesa.com/"
    }
    try:
        res = requests.get(url, headers=headers, timeout=20)
        return res.json() if res.status_code == 200 else []
    except:
        return []

def vibe_check():
    SPORTS = [1, 2, 4, 5]
    batch = []

    print("📡 Lucra Scout: Syncing heroes from Sportpesa...")

    for sid in SPORTS:
        data = fetch_heroes(sid)
        if not isinstance(data, list): continue

        for item in data:
            # Safely navigate the JSON structure you provided
            markets = item.get('markets', [])
            h_odd, d_odd, a_odd = 0.0, 0.0, 0.0
            
            # Extract 1X2 from the '3 Way' market
            if markets and markets[0].get('name') == '3 Way':
                selections = markets[0].get('selections', [])
                h_odd = float(next((s['odds'] for s in selections if s['shortName'] == '1'), 0))
                d_odd = float(next((s['odds'] for s in selections if s['shortName'] == 'X'), 0))
                a_odd = float(next((s['odds'] for s in selections if s['shortName'] == '2'), 0))

            batch.append({
                "game_id": str(item.get('id')),
                "sport_id": sid,
                "competition": clean_text(item.get('competition', {}).get('name')),
                "home_team": clean_text(item.get('competitors', [{}])[0].get('name')),
                "away_team": clean_text(item.get('competitors', [{}, {}])[1].get('name')),
                "match_date": item.get('date'), # e.g., "2026-04-13T19:00:00.000Z"
                "market_1": h_odd,
                "market_x": d_odd,
                "market_2": a_odd,
                "all_markets": markets, # Keep full JSON for the deep scraper
                "last_updated": datetime.now().isoformat()
            })

    if batch:
        # Upsert ensures we update existing games and add new ones
        supabase.table("sp_prematch_master").upsert(batch, on_conflict="game_id").execute()
        print(f"✅ Success! {len(batch)} heroes are now in Lucra.")
        
        # Cleanup: Remove heroes that are 5 hours old
        cutoff = (datetime.now() - timedelta(hours=5)).isoformat()
        supabase.table("sp_prematch_master").delete().lt("match_date", cutoff).execute()
        print("🧹 Cleanup: Old match data pruned.")
    else:
        print("⚠️ No heroes found. Verify endpoint status.")

if __name__ == "__main__":
    vibe_check()
