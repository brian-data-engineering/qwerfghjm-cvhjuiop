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
    """The Stealth Worker: Fetches and pushes one match at a time."""
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"
    ]

    session = requests.Session()
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": f"https://1xbet.co.ke/en/line/football/{m_id}",
        "User-Agent": random.choice(agents),
        "X-Requested-With": "XMLHttpRequest"
    })

    url = "https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents"
    params = {
        "cfView": "3", "countEvents": "250", "country": "87", 
        "gameId": str(m_id), "gr": "657", "grMode": "4", 
        "lng": "en", "marketType": "1", "ref": "61"
    }
    
    try:
        # HUMAN JITTER: Mimic a person clicking through matches
        time.sleep(random.uniform(2.5, 5.0))
        
        resp = session.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            rows = []
            
            def extract(groups, period, sub_id):
                if not groups: return
                for g in groups:
                    gid = g.get("groupId")
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

            extract(data.get("eventGroups", []), "Full Time", m_id)
            for sub in data.get("subGamesForMainGame", []):
                extract(sub.get("eventGroups", []), sub.get("subGameName", "Unknown"), sub.get("id"))

            if rows:
                supabase.table("xmatch_odds_deep").upsert(rows).execute()
                # FLUSH=TRUE forces the log to appear immediately
                print(f"[LIVE] Match {m_id} -> Success ({len(rows)} markets)", flush=True)
                return len(rows)
            else:
                print(f"[EMPTY] Match {m_id} -> No markets found", flush=True)
        else:
            print(f"[BLOCKED] Match {m_id} -> Status {resp.status_code}", flush=True)
            
    except Exception as e:
        print(f"[ERROR] Match {m_id} -> {str(e)}", flush=True)
    return 0

def run():
    print("--- Lucra Stealth Sync Starting ---", flush=True)
    
    print("Clearing old data...", flush=True)
    try:
        supabase.table("xmatch_odds_deep").delete().neq("match_id", 0).execute()
    except Exception as e:
        print(f"Purge Warning: {e}", flush=True)

    # Fetch IDs
    res = supabase.table("xmatch_odds").select("match_id").execute()
    ids = [r['match_id'] for r in res.data]
    
    # SHUFFLE the IDs so the scraping pattern is random
    random.shuffle(ids)
    
    print(f"Ready to sync {len(ids)} matches using 3 workers...", flush=True)

    # Using 3 workers for safety and visibility
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(fetch_and_upload, ids))

    total = sum(results)
    print(f"\n--- SYNC FINISHED ---", flush=True)
    print(f"Total Market Rows Saved: {total}", flush=True)

if __name__ == "__main__":
    run()
