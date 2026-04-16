import os
import requests
import concurrent.futures
from datetime import datetime
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def fetch_and_upload(m_id):
    """Worker that fetches a match and pushes to Supabase immediately"""
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
    
    try:
        resp = session.get(url, params=params, timeout=10)
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

            # Full Time + Sub Games
            extract(data.get("eventGroups", []), "Full Time", m_id)
            for sub in data.get("subGamesForMainGame", []):
                extract(sub.get("eventGroups", []), sub.get("subGameName", "Unknown"), sub.get("id"))

            if rows:
                # Upsert immediately so you see data moving in Supabase
                supabase.table("xmatch_odds_deep").upsert(rows).execute()
                return len(rows)
    except Exception:
        pass 
    return 0

def run():
    # 1. Clear old data (Fast delete)
    print("Clearing old markets...")
    try:
        supabase.table("xmatch_odds_deep").delete().neq("match_id", 0).execute()
    except:
        pass

    # 2. Get IDs
    res = supabase.table("xmatch_odds").select("match_id").execute()
    ids = [r['match_id'] for r in res.data]
    
    print(f"Turbo-Syncing {len(ids)} matches...")

    # 3. Use 20 workers for maximum speed
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(fetch_and_upload, ids))

    print(f"Lucra Deep-Sync Finished. Total rows: {sum(results)}")

if __name__ == "__main__":
    run()
