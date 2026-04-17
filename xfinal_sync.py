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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0",
    "Accept": "application/json",
    "Connection": "keep-alive"
})

def vacuum_match(m_id):
    url = "https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents"
    params = {
        "cfView": "3", "countEvents": "250", "country": "87", 
        "gameId": str(m_id), "gr": "657", "grMode": "4", 
        "lng": "en", "marketType": "1", "ref": "61"
    }
    
    try:
        resp = session.get(url, params=params, timeout=12)
        if resp.status_code != 200: return 0
            
        data = resp.json().get("Value", {})
        rows = []
        
        # This function ignores logic and just collects everything
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
                                "event_type": int(e.get("type", 0)),
                                "parameter": float(e.get("parameter", 0)),
                                "odds": float(e.get("cf")),
                                "raw_json": e, # THE SAFETY NET: Save the whole object
                                "scraped_at": datetime.now().isoformat()
                            })

        # Suck up Main Events
        collect(data.get("GE", []), "Full Time", m_id)
        
        # Suck up every Sub Game (1st Half, Corners, etc.)
        for sub in data.get("subGamesForMainGame", []):
            collect(sub.get("eventGroups", []), sub.get("subGameName", "Unknown"), sub.get("id"))

        if rows:
            # Upsert everything. The unique constraint handles the 'sorting' for us.
            supabase.table("xmatch_odds_deep").upsert(
                rows, 
                on_conflict="match_id,period,group_id,event_type,parameter"
            ).execute()
            return len(rows)
            
    except Exception:
        pass
    return 0

def run():
    res = supabase.table("xmatch_odds").select("deep_game_id").not_.is_("deep_game_id", "null").execute()
    ids = [r['deep_game_id'] for r in res.data]
    
    print(f"Vacuuming {len(ids)} games into Lucra...")

    # Using 15 workers to stay under your 10-minute deadline
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        results = list(executor.map(vacuum_match, ids))

    print(f"Finished. Total outcomes archived: {sum(results)}")

if __name__ == "__main__":
    run()
