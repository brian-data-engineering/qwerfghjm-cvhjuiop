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
    # Cleaning quotes to prevent SQL/JSON breaks in the 'Lucra' database
    return str(text).replace('"', '').replace("'", "").strip()

def fetch_heroes(sport_id):
    session = requests.Session()
    url = f"https://ke.sportpesa.com/api/upcoming/games?sportId={sport_id}"
    
    # Standard browser-impersonating headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://ke.sportpesa.com/",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }

    try:
        # Pacing to mimic human browsing behavior
        time.sleep(random.uniform(1.5, 3.5))
        
        res = session.get(url, headers=headers, timeout=30)
        
        print(f"📡 Scout hitting: {url}")
        print(f"📊 Status: {res.status_code} | Length: {len(res.text)}")

        if res.status_code == 200:
            content = res.text.strip()
            if not content:
                return []
            
            data = res.json()
            # FIX: Handle the 'direct list' format found in your recent logs
            return data if isinstance(data, list) else data.get('games', [])
                
    except Exception as e:
        print(f"⚠️ Scout Error on ID {sport_id}: {str(e)}")
            
    return []

def vibe_check():
    # 1: Football, 2: Basketball, 4: Rugby, 5: Tennis
    SPORTS = [1, 2, 4, 5]
    batch = []
    seen_ids = set()

    print("📡 Lucra Scout: Syncing heroes from Sportpesa...")

    for sid in SPORTS:
        games = fetch_heroes(sid)
        if not games: continue

        for item in games:
            game_id = str(item.get('id'))
            if game_id in seen_ids: continue
            
            markets = item.get('markets', [])
            h_odd, d_odd, a_odd = 0.0, 0.0, 0.0
            
            if markets:
                # Target the primary market (usually first in the list)
                main_market = markets[0]
                m_name = main_market.get('name', '')
                selections = main_market.get('selections', [])
                
                # Logic for 3 Way (Football/Rugby)
                if m_name == '3 Way':
                    try:
                        h_odd = float(next((s['odds'] for s in selections if s['shortName'] == '1'), 0))
                        d_odd = float(next((s['odds'] for s in selections if s['shortName'] == 'X'), 0))
                        a_odd = float(next((s['odds'] for s in selections if s['shortName'] == '2'), 0))
                    except (StopIteration, ValueError, KeyError): pass
                
                # Logic for 2 Way (Basketball/Tennis)
                elif '2 Way' in m_name:
                    try:
                        h_odd = float(next((s['odds'] for s in selections if s['shortName'] == '1'), 0))
                        a_odd = float(next((s['odds'] for s in selections if s['shortName'] == '2'), 0))
                        d_odd = 0.0 # No draw in 2-way sports
                    except (StopIteration, ValueError, KeyError): pass

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
                "all_markets": markets, # Stores full JSON for future 'editable' updates
                "last_updated": datetime.now().isoformat()
            })
            seen_ids.add(game_id)

    if batch:
        try:
            # Upsert into sp_prematch_master
            supabase.table("sp_prematch_master").upsert(batch, on_conflict="game_id").execute()
            print(f"✅ Success! {len(batch)} heroes are now in Lucra.")
            
            # Maintenance: Remove games that started more than 5 hours ago
            cutoff = (datetime.now() - timedelta(hours=5)).isoformat()
            supabase.table("sp_prematch_master").delete().lt("match_date", cutoff).execute()
            print("🧹 Cleanup: Old match data pruned.")
        except Exception as e:
            print(f"🚨 Supabase Error: {e}")
    else:
        print("🕵️ Scout report: No data captured.")

if __name__ == "__main__":
    vibe_check()
