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

def fetch_deep_odds(m_id):
    session = requests.Session()
    # These headers are the "Golden Key" to make 1xBet treat the script like a browser
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://1xbet.co.ke/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    })

    url = "https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents"
    
    # EXACT params from your successful manual link
    params = {
        "cfView": "3",
        "countEvents": "250",
        "country": "87",
        "gameId": str(m_id),
        "gr": "657",     # Group Routing
        "grMode": "4",
        "lng": "en",
        "marketType": "1",
        "ref": "61"      # Reference ID
    }
    
    all_payloads = []
    try:
        # Reduced frequency: jitter helps bypass "anti-scraping" patterns
        time.sleep(random.uniform(0.1, 0.4))
        
        resp = session.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            
            # The structure we found: it's flat, so we look for eventGroups directly
            def process_groups(groups, period_name, sub_id):
                rows = []
                if not groups: return rows
                for g in groups:
                    gid = g.get("groupId")
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
            all_payloads.extend(process_groups(data.get("eventGroups", []), "Full Time", m_id))

            # 2. Sub Games (1st Half, 2nd Half, etc.)
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
    print("Clearing old data...")
    supabase.table("xmatch_odds_deep").delete().neq("match_id", 0).execute()

    # Get IDs from your validated xmatch_odds table
    res = supabase.table("xmatch_odds").select("match_id").execute()
    ids = [r['match_id'] for r in res.data]
    
    print(f"Syncing deep markets for {len(ids)} matches...")

    # Using 5 workers to stay under the radar
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
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
