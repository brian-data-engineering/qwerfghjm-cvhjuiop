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
    res = supabase.table("xmatch_odds").select("match_id").execute()
    return [r['match_id'] for r in res.data]

def fetch_deep_odds(m_id):
    # Using the exact URL and parameters from your successful sample
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
        resp = session.get(url, params=params, timeout=12)
        if resp.status_code == 200:
            data = resp.json() # Direct root access
            
            def process_groups(groups, period_name, sub_id):
                rows = []
                if not groups: return rows
                for g in groups:
                    gid = g.get("groupId")
                    # events is a list of lists [[{...}]]
                    for event_list in g.get("events", []):
                        for e in event_list:
                            if e and 'cf' in e:
                                rows.append({
                                    "match_id": m_id,
                                    "sub_id": sub_id,
                                    "period": period_name,
                                    "group_id": gid,
                                    "raw_data": e,
                                    "scraped_at": datetime.now().isoformat()
                                })
                return rows

            # 1. Main Game (Full Time)
            main_groups = data.get("eventGroups", [])
            all_payloads.extend(process_groups(main_groups, "Full Time", m_id))

            # 2. Sub Games (Halves, Corners, First To Happen)
            for sub in data.get("subGamesForMainGame", []):
                all_payloads.extend(process_groups(
                    sub.get("eventGroups", []), 
                    sub.get("subGameName", "Unknown"), 
                    sub.get("id")
                ))
    except Exception as err:
        pass 
    return all_payloads

def run():
    # Clear old data - simplified for reliability
    print("Clearing old data...")
    try:
        supabase.table("xmatch_odds_deep").delete().neq("match_id", 0).execute()
    except:
        pass

    ids = get_pending_ids()
    print(f"Syncing deep markets for {len(ids)} matches...")

    # We use 10 workers to stay safe from rate limits
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_deep_odds, ids))

    # Flatten results
    final_data = [item for sublist in results for item in sublist if sublist]
    
    print(f"Collected {len(final_data)} total market events.")

    if final_data:
        # Upload in chunks of 2000 for Supabase stability
        for i in range(0, len(final_data), 2000):
            chunk = final_data[i:i + 2000]
            try:
                supabase.table("xmatch_odds_deep").upsert(chunk).execute()
            except Exception as e:
                print(f"Chunk error: {e}")

    print("Lucra Deep-Sync Finished.")

if __name__ == "__main__":
    run()
