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
    "Accept": "application/json"
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
        
        def collect(groups, period_name, s_id):
            for g in groups or []:
                gid = g.get("groupId")
                for sublist in g.get("events", []):
                    for e in sublist:
                        if e and e.get('cf'):
                            # Mapping only to the 7 columns your table actually has
                            rows.append({
                                "match_id": int(m_id),
                                "sub_id": int(s_id or m_id),
                                "period": str(period_name),
                                "group_id": int(gid or 0),
                                "raw_data": e, # This stores type, cf, and parameter together
                                "scraped_at": datetime.now().isoformat()
                            })

        # 1. Main Game
        collect(data.get("GE", []), "Full Time", m_id)
        
        # 2. Sub Games
        for sub in data.get("subGamesForMainGame", []):
            collect(sub.get("eventGroups", []), sub.get("subGameName", "Unknown"), sub.get("id"))

        if rows:
            # Batch upsert
            supabase.table("xmatch_odds_deep").insert(rows).execute()
            return len(rows)
            
    except Exception as e:
        print(f"Error on {m_id}: {e}")
    return 0

def run():
    res = supabase.table("xmatch_odds").select("deep_game_id").not_.is_("deep_game_id", "null").limit(1000).execute()
    ids = [r['deep_game_id'] for r in res.data]
    
    print(f"Vacuuming {len(ids)} games into Lucra...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        results = list(executor.map(vacuum_match, ids))

    print(f"Finished. Total rows added: {sum(results)}")

if __name__ == "__main__":
    run()
