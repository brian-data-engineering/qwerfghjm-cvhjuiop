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
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ]

    session.headers.update({
        "Accept": "application/json",
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
        # Balanced jitter: Enough to stay under the radar, fast enough to finish
        time.sleep(random.uniform(2.0, 5.0))
        
        resp = session.get(url, params=params, timeout=30)
        if resp.status_code != 200 or not resp.text.strip():
            return 0
            
        json_data = resp.json()
        # Navigate to the 'Value' container safely
        value_data = json_data.get("Value", {})
        
        rows = []
        
        def extract_logic(groups, period_name, sub_id):
            if not groups: return
            for g in groups:
                gid = g.get("groupId")
                if gid is None: continue # Skip if no group ID
                
                for event_list in g.get("events", []):
                    for e in event_list:
                        # CRITICAL: Only proceed if odds (cf) and type exist
                        if e and e.get('cf') and e.get('type'):
                            rows.append({
                                "match_id": int(m_id),
                                "sub_id": int(sub_id) if sub_id else int(m_id),
                                "period": str(period_name) if period_name else "Full Time",
                                "group_id": int(gid),
                                "event_type": int(e.get("type")),
                                "parameter": float(e.get("parameter", 0)), # Use 0 instead of NULL
                                "odds": float(e.get("cf")),
                                "scraped_at": datetime.now().isoformat()
                            })

        # 1. Scrape Main Events (usually 1x2, Double Chance)
        extract_logic(value_data.get("GE", []), "Full Time", m_id)
        
        # 2. Scrape Sub Games (Corners, Cards, etc.)
        for sub in value_data.get("subGamesForMainGame", []):
            extract_logic(
                sub.get("eventGroups", []), 
                sub.get("subGameName", "Other"), 
                sub.get("id")
            )

        if rows:
            # Upserting in chunks of 400 to keep the request size safe
            for i in range(0, len(rows), 400):
                supabase.table("xmatch_odds_deep").upsert(
                    rows[i:i+400], 
                    on_conflict="match_id,period,group_id,event_type"
                ).execute()
            return len(rows)
            
    except Exception as e:
        print(f"Skipping {m_id} due to error: {e}")
    return 0

def run():
    print("--- Lucra Deep-Market Sync 2.0 (No-Null Mode) ---")
    
    # Target only matches we know have a valid deep ID
    res = supabase.table("xmatch_odds").select("deep_game_id").not_.is_("deep_game_id", "null").execute()
    ids = [r['deep_game_id'] for r in res.data]
    random.shuffle(ids)
    
    print(f"Targeting {len(ids)} deep games...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(fetch_and_upload, ids))

    print(f"Done. Total outcomes saved: {sum(results)}")

if __name__ == "__main__":
    run()
