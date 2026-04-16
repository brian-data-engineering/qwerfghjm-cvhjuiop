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
    # Harder browser fingerprint
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Host": "1xbet.co.ke",
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
    
    try:
        time.sleep(random.uniform(1.0, 2.0))
        resp = session.get(url, params=params, timeout=25)
        
        # DIAGNOSTIC PRINT: Let's see what we are actually getting
        if resp.status_code != 200:
            print(f"[HTTP {resp.status_code}] Match {m_id} failed connection.", flush=True)
            return 0
            
        data = resp.json()
        
        # Check if 1xBet sent an empty success response (common bot block)
        if not data or ("eventGroups" not in data and "subGamesForMainGame" not in data):
            print(f"[EMPTY_JSON] Match {m_id} returned 200 but no data keys.", flush=True)
            return 0

        rows = []
        seen_in_batch = set()
        
        def extract(groups, period, sub_id):
            if not groups: return
            for g in groups:
                gid = g.get("groupId")
                key = (m_id, period, gid)
                if key in seen_in_batch: continue
                
                for event_list in g.get("events", []):
                    for e in event_list:
                        if e and 'cf' in e:
                            rows.append({
                                "match_id": m_id, "sub_id": sub_id, "period": period,
                                "group_id": gid, "raw_data": e, "scraped_at": datetime.now().isoformat()
                            })
                            seen_in_batch.add(key)
                            break 

        extract(data.get("eventGroups", []), "Full Time", m_id)
        for sub in data.get("subGamesForMainGame", []):
            extract(sub.get("eventGroups", []), sub.get("subGameName", "Unknown"), sub.get("id"))

        if rows:
            # We use a try/except specifically for the DB push to see if Supabase is the bottleneck
            try:
                supabase.table("xmatch_odds_deep").upsert(rows).execute()
                print(f"[SUCCESS] Match {m_id} -> {len(rows)} markets saved.", flush=True)
                return len(rows)
            except Exception as db_e:
                print(f"[DB_ERROR] Match {m_id} -> {str(db_e)[:100]}", flush=True)
        else:
            print(f"[NO_MARKETS] Match {m_id} had JSON but no 'cf' odds found.", flush=True)
            
    except Exception as e:
        print(f"[FATAL] Match {m_id} crash: {str(e)[:50]}", flush=True)
    return 0

def run():
    print("--- Lucra Diagnostic Start ---", flush=True)
    
    # Check if IDs even exist
    res = supabase.table("xmatch_odds").select("match_id").limit(1000).execute()
    ids = [r['match_id'] for r in res.data]
    
    if not ids:
        print("[CRITICAL] xmatch_odds table is empty! Nothing to sync.", flush=True)
        return

    print(f"Testing {len(ids)} matches with 4 workers...", flush=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(fetch_and_upload, ids))

    print(f"\n--- Sync Result: {sum(results)} total rows ---", flush=True)

if __name__ == "__main__":
    run()
