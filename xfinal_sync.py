import os
import requests
import concurrent.futures
from datetime import datetime
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

session = requests.Session()
session.headers.update({
    "Referer": "https://1xbet.co.ke/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})

def get_pending_ids():
    """Get the 3,322 IDs from our metadata table."""
    res = supabase.table("xmatch_odds").select("match_id").execute()
    return [r['match_id'] for r in res.data]

def fetch_deep_odds(m_id):
    """The 'Get Everything' scraper worker."""
    url = "https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents"
    params = {
        "cfView": "3",
        "countEvents": "250",
        "country": "87",
        "gameId": str(m_id),
        "grMode": "4",
        "lng": "en",
        "marketType": "1",
        "ref": "61"
    }
    
    all_payloads = []
    try:
        resp = session.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("Value", {})
            
            # Helper to extract group events
            def process_groups(groups, period_name, sub_id):
                rows = []
                for g in groups:
                    gid = g.get("groupId")
                    for event_list in g.get("events", []):
                        for e in event_list:
                            rows.append({
                                "match_id": m_id,
                                "sub_id": sub_id,
                                "period": period_name,
                                "group_id": gid,
                                "raw_data": e,
                                "scraped_at": datetime.now().isoformat()
                            })
                return rows

            # 1. Full Time
            all_payloads.extend(process_groups(data.get("eventGroups", []), "Full Time", m_id))

            # 2. Sub Games (Halves, Corners, etc)
            for sub in data.get("subGamesForMainGame", []):
                all_payloads.extend(process_groups(
                    sub.get("eventGroups", []), 
                    sub.get("subGameName", "Unknown"), 
                    sub.get("id")
                ))
    except Exception:
        pass
    return all_payloads

def run():
    # 1. Clear old odds to keep Supabase storage free
    print("Clearing old deep odds...")
    supabase.table("xmatch_odds_deep").delete().neq("match_id", 0).execute()

    ids = get_pending_ids()
    print(f"Starting Deep Sync for {len(ids)} matches...")

    final_data = []
    # 10 threads is safe for Deep Sync
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_deep_odds, ids))

    for r in results:
        final_data.extend(r)

    print(f"Total Deep Market rows collected: {len(final_data)}")

    # 2. Upsert in large chunks
    for i in range(0, len(final_data), 2000):
        chunk = final_data[i:i + 2000]
        try:
            supabase.table("xmatch_odds_deep").upsert(chunk).execute()
        except Exception as e:
            print(f"Upload error: {e}")

    print("Lucra Deep-Sync Finished.")

if __name__ == "__main__":
    run()
