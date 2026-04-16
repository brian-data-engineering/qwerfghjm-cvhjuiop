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
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ]

    session = requests.Session()
    session.headers.update({
        "Accept": "application/json",
        "Referer": "https://1xbet.co.ke/",
        "User-Agent": random.choice(agents),
        "X-Requested-With": "XMLHttpRequest"
    })

    url = "https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents"
    params = {"cfView": "3", "countEvents": "250", "country": "87", "gameId": str(m_id), "gr": "657", "grMode": "4", "lng": "en", "marketType": "1", "ref": "61"}
    
    try:
        # 2-4 second sleep mimics a human "thinking" time
        time.sleep(random.uniform(2.0, 4.0))
        
        resp = session.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            rows = []
            
            def extract(groups, period, sub_id):
                for g in groups or []:
                    gid = g.get("groupId")
                    for event_list in g.get("events", []):
                        for e in event_list:
                            if e and 'cf' in e:
                                rows.append({
                                    "match_id": m_id, "sub_id": sub_id, "period": period,
                                    "group_id": gid, "raw_data": e, "scraped_at": datetime.now().isoformat()
                                })

            extract(data.get("eventGroups", []), "Full Time", m_id)
            for sub in data.get("subGamesForMainGame", []):
                extract(sub.get("eventGroups", []), sub.get("subGameName", "Unknown"), sub.get("id"))

            if rows:
                supabase.table("xmatch_odds_deep").upsert(rows).execute()
                # THIS IS THE PROGRESS BAR:
                print(f"[LIVE] Match {m_id} synced: {len(rows)} markets found.")
                return len(rows)
            else:
                print(f"[EMPTY] Match {m_id} returned no markets.")
    except Exception as e:
        print(f"[ERROR] Match {m_id} failed: {e}")
    return 0

def run():
    print("Purging old markets...")
    supabase.table("xmatch_odds_deep").delete().neq("match_id", 0).execute()

    res = supabase.table("xmatch_odds").select("match_id").execute()
    ids = [r['match_id'] for r in res.data]
    random.shuffle(ids)
    
    print(f"Starting Stealth Sync on {len(ids)} matches...")

    # 3 Workers = Low risk, visible progress
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        # Use list() to force the generator to start and print logs immediately
        results = list(executor.map(fetch_and_upload, ids))

    print(f"--- FINISHED ---")
    print(f"Total Markets Saved: {sum(results)}")

if __name__ == "__main__":
    run()
