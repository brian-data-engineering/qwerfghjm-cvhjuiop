import os
import requests
import concurrent.futures
import time
from datetime import datetime
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

# Connection Pool - CRITICAL for speed
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=30)
session.mount('https://', adapter)

def fetch_and_upload(m_id):
    url = "https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents"
    params = {
        "cfView": "3", "countEvents": "250", "country": "87", 
        "gameId": str(m_id), "gr": "657", "grMode": "4", 
        "lng": "en", "marketType": "1", "ref": "61"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
        "X-Requested-With": "XMLHttpRequest"
    }
    
    # Try twice for timeouts
    for attempt in range(2):
        try:
            resp = session.get(url, params=params, timeout=15, headers=headers)
            if resp.status_code != 200: return 0
                
            json_data = resp.json()
            value_data = json_data.get("Value", {})
            rows = []
            
            def extract_logic(groups, period_name, sub_id):
                if not groups: return
                for g in groups:
                    gid = g.get("groupId")
                    if gid is None: continue
                    for event_list in g.get("events", []):
                        for e in event_list:
                            if e and e.get('cf') and e.get('type'):
                                rows.append({
                                    "match_id": int(m_id),
                                    "sub_id": int(sub_id or m_id),
                                    "period": str(period_name),
                                    "group_id": int(gid),
                                    "event_type": int(e.get("type")),
                                    "parameter": float(e.get("parameter", 0)),
                                    "odds": float(e.get("cf")),
                                    "scraped_at": datetime.now().isoformat()
                                })

            extract_logic(value_data.get("GE", []), "Full Time", m_id)
            for sub in value_data.get("subGamesForMainGame", []):
                extract_logic(sub.get("eventGroups", []), sub.get("subGameName", "Other"), sub.get("id"))

            if rows:
                supabase.table("xmatch_odds_deep").upsert(rows, on_conflict="match_id,period,group_id,event_type").execute()
                return len(rows)
            return 0

        except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectTimeout):
            if attempt == 0:
                time.sleep(1) # Quick pause before one retry
                continue
        except Exception:
            break
    return 0

def run():
    print(f"--- Lucra Turbo Sync (10 Min Target) ---")
    
    res = supabase.table("xmatch_odds").select("deep_game_id").not_.is_("deep_game_id", "null").execute()
    ids = [r['deep_game_id'] for r in res.data]
    
    # Process 1000 games
    print(f"Syncing {len(ids)} games with 15 workers...")

    # 15 workers is the sweet spot. 20+ causes too many timeouts.
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        results = list(executor.map(fetch_and_upload, ids))

    print(f"Done. Outcomes saved: {sum(results)}")

if __name__ == "__main__":
    run()
