import os
import requests
import json
import sys
from datetime import datetime
from supabase import create_client, Client

# --- FORCE LOGGING ---
print("--- SCRIPT STARTING ---")

# Config Check
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")

if not URL or not KEY:
    print("ERROR: Supabase Environment Variables are MISSING!")
    sys.exit(1)

supabase: Client = create_client(URL, KEY)

def vacuum_match(m_id):
    url = "https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents"
    params = {
        "cfView": "3", "countEvents": "250", "country": "87",
        "gameId": str(m_id), "gr": "657", "grMode": "4",
        "lng": "en", "marketType": "1", "ref": "61"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://1xbet.co.ke/en/line"
    }

    print(f"Checking ID: {m_id}")
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        print(f"ID {m_id} -> Status: {resp.status_code}")
        
        if resp.status_code == 200:
            raw_json = resp.json()
            # Double-check the structure you confirmed in the browser
            data_source = raw_json.get("Value") if raw_json.get("Value") else raw_json
            
            sub_games = data_source.get("subGamesForMainGame", [])
            if not sub_games:
                print(f"ID {m_id} -> No subGames found in JSON.")
                return 0
            
            rows = []
            for sub in sub_games:
                period_name = sub.get("subGameName", "SubGame")
                s_id = sub.get("id", m_id)
                for group in sub.get("eventGroups", []):
                    gid = group.get("groupId")
                    for sublist in group.get("events", []):
                        for e in sublist:
                            if e and e.get('cf'):
                                rows.append({
                                    "match_id": int(m_id),
                                    "sub_id": int(s_id),
                                    "period": str(period_name),
                                    "group_id": int(gid or 0),
                                    "raw_data": e,
                                    "scraped_at": datetime.now().isoformat()
                                })
            
            if rows:
                supabase.table("xmatch_odds_deep").insert(rows).execute()
                print(f"ID {m_id} -> INSERTED {len(rows)} rows.")
                return len(rows)
    except Exception as e:
        print(f"ID {m_id} -> EXCEPTION: {e}")
    return 0

if __name__ == "__main__":
    # Get IDs from your table
    print("Fetching IDs from Supabase...")
    res = supabase.table("xmatch_odds").select("deep_game_id").not_.is_("deep_game_id", "null").limit(5).execute()
    
    ids = [r['deep_game_id'] for r in res.data]
    print(f"Found {len(ids)} IDs to process: {ids}")

    if not ids:
        print("No IDs found. Exiting.")
        sys.exit(0)

    total = 0
    for m_id in ids:
        total += vacuum_match(m_id)
    
    print(f"--- SCRIPT FINISHED. TOTAL CAPTURED: {total} ---")
