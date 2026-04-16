import os
import requests
import concurrent.futures
import time
import random
from datetime import datetime
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def fetch_and_upload(m_id):
    session = requests.Session()
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://1xbet.co.ke/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    })

    url = "https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents"
    params = {
        "cfView": "3", "countEvents": "250", "country": "87", 
        "gameId": str(m_id), "gr": "657", "grMode": "4", 
        "lng": "en", "marketType": "1", "ref": "61"
    }
    
    # Retry logic for Timeouts
    for attempt in range(2): 
        try:
            # Subtle jitter
            time.sleep(random.uniform(0.5, 1.5))
            
            resp = session.get(url, params=params, timeout=20) # Increased timeout
            if resp.status_code == 200:
                data = resp.json()
                seen_keys = set()
                rows = []
                
                def extract(groups, period, sub_id):
                    if not groups: return
                    for g in groups:
                        gid = g.get("groupId")
                        # Unique Key Check: prevents the Duplicate Key error
                        key = (m_id, period, gid)
                        if key in seen_keys: continue
                        
                        for event_list in g.get("events", []):
                            for e in event_list:
                                if e and 'cf' in e:
                                    rows.append({
                                        "match_id": m_id,
                                        "sub_id": sub_id,
                                        "period": period,
                                        "group_id": gid,
                                        "raw_data": e,
                                        "scraped_at": datetime.now().isoformat()
                                    })
                                    seen_keys.add(key)
                                    break # We only need one entry per group/period

                extract(data.get("eventGroups", []), "Full Time", m_id)
                for sub in data.get("subGamesForMainGame", []):
                    extract(sub.get("eventGroups", []), sub.get("subGameName", "Unknown"), sub.get("id"))

                if rows:
                    supabase.table("xmatch_odds_deep").upsert(rows).execute()
                    print(f"[LIVE] Match {m_id} -> {len(rows)} markets", flush=True)
                    return len(rows)
                return 0
        except Exception as e:
            if attempt == 1:
                print(f"[ERROR] Match {m_id} -> {str(e)}", flush=True)
    return 0

def run():
    print("Purging old markets...", flush=True)
    try:
        supabase.table("xmatch_odds_deep").delete().neq("match_id", 0).execute()
    except: pass

    res = supabase.table("xmatch_odds").select("match_id").execute()
    ids = [r['match_id'] for r in res.data]
    random.shuffle(ids)
    
    print(f"Syncing {len(ids)} matches with Duplicate Protection...", flush=True)

    # Balanced speed: 8 workers is fast but stable
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(fetch_and_upload, ids))

    print(f"\n--- FINISHED --- Total Markets: {sum(results)}", flush=True)

if __name__ == "__main__":
    run()
