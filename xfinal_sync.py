import os
import requests
import concurrent.futures
from datetime import datetime
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def vacuum_match(m_id):
    # THE URL: Strictly using the main-line-feed structure you provided
    url = "https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents"
    
    params = {
        "cfView": "3",
        "countEvents": "250",
        "country": "87",
        "gameId": str(m_id),
        "gr": "657",
        "grMode": "4",
        "lng": "en",
        "marketType": "1",
        "ref": "61"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
        "X-Requested-With": "XMLHttpRequest"
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        
        # If the status is not 200 (like a 400 Bad Request), log it and skip to next
        if resp.status_code != 200:
            error_json = resp.json() if resp.text else {"status": resp.status_code}
            supabase.table("xmatch_odds_deep").insert({
                "match_id": int(m_id),
                "period": "BAD_REQUEST",
                "raw_data": error_json, # Captures that 400 error JSON
                "scraped_at": datetime.now().isoformat()
            }).execute()
            return 0

        data = resp.json().get("Value")
        if not data:
            return 0

        rows = []
        def collect(groups, period, s_id):
            for g in groups or []:
                gid = g.get("groupId")
                for sublist in g.get("events", []):
                    for e in sublist:
                        if e and e.get('cf'):
                            rows.append({
                                "match_id": int(m_id),
                                "sub_id": int(s_id or m_id),
                                "period": str(period),
                                "group_id": int(gid or 0),
                                "raw_data": e,
                                "scraped_at": datetime.now().isoformat()
                            })

        collect(data.get("GE"), "Full Time", m_id)
        for sub in data.get("subGamesForMainGame", []):
            collect(sub.get("eventGroups"), sub.get("subGameName", "SubGame"), sub.get("id"))

        if rows:
            supabase.table("xmatch_odds_deep").insert(rows).execute()
            return len(rows)

    except Exception:
        pass
    return 0

def run():
    res = supabase.table("xmatch_odds").select("deep_game_id").not_.is_("deep_game_id", "null").limit(1000).execute()
    ids = [r['deep_game_id'] for r in res.data]
    
    print(f"Lucra Scan: Processing {len(ids)} IDs...")

    # Maximum speed: 20 workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(vacuum_match, ids))

    print(f"Finished. Total outcomes archived: {sum(results)}")

if __name__ == "__main__":
    run()
