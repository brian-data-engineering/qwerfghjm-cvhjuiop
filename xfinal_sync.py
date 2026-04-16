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
    # Use a fresh session for EVERY match to clear session tracking
    session = requests.Session()
    
    # Randomize User-Agents to prevent "Signature" fingerprinting
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ]

    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://1xbet.co.ke/",
        "User-Agent": random.choice(user_agents),
        "X-Requested-With": "XMLHttpRequest"
    })

    url = "https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents"
    params = {
        "cfView": "3", "countEvents": "250", "country": "87", 
        "gameId": str(m_id), "gr": "657", "grMode": "4", 
        "lng": "en", "marketType": "1", "ref": "61"
    }
    
    try:
        # THE FIX: Longer, more varied jitter. 
        # This makes it impossible for them to find a "pattern."
        time.sleep(random.uniform(5.0, 12.0))
        
        resp = session.get(url, params=params, timeout=30)
        
        if not resp.text.strip():
            print(f"[BLOCKED] Match {m_id} -> Empty Response (Throttled)", flush=True)
            return 0
            
        data = resp.json()
        rows = []
        seen_keys = set()
        
        def extract(groups, period, sub_id):
            for g in groups or []:
                gid = g.get("groupId")
                key = (m_id, period, gid)
                if key in seen_keys: continue
                for event_list in g.get("events", []):
                    for e in event_list:
                        if e and 'cf' in e:
                            rows.append({
                                "match_id": m_id, "sub_id": sub_id, "period": period,
                                "group_id": gid, "raw_data": e, "scraped_at": datetime.now().isoformat()
                            })
                            seen_keys.add(key)
                            break 

        extract(data.get("eventGroups", []), "Full Time", m_id)
        for sub in data.get("subGamesForMainGame", []):
            extract(sub.get("eventGroups", []), sub.get("subGameName", "Unknown"), sub.get("id"))

        if rows:
            # upsert with ignore to handle the duplicates silently
            supabase.table("xmatch_odds_deep").upsert(rows, on_conflict="match_id,period,group_id").execute()
            print(f"[SUCCESS] Match {m_id} -> {len(rows)} markets saved.", flush=True)
            return len(rows)
            
    except Exception as e:
        # This catches the "char 0" JSON error without crashing the script
        print(f"[RETRY_NEEDED] Match {m_id} -> Invalid response format.", flush=True)
    return 0

def run():
    print("--- Lucra Stealth-Mode 2.0 ---", flush=True)
    
    res = supabase.table("xmatch_odds").select("match_id").execute()
    ids = [r['match_id'] for r in res.data]
    random.shuffle(ids) # Random order is CRITICAL to avoid detection
    
    print(f"Syncing {len(ids)} matches with 2 workers (Ultra-Stealth)...", flush=True)

    # DROPPING TO 2 WORKERS. 
    # This is the "Safety Zone" to keep the IP from getting flagged.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(fetch_and_upload, ids))

    print(f"\n--- Sync Complete --- Total: {sum(results)}", flush=True)

if __name__ == "__main__":
    run()
