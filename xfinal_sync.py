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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "X-Requested-With": "XMLHttpRequest"
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
        
        # Check 1: Is the request actually working?
        if resp.status_code != 200:
            print(f"HTTP ERROR {resp.status_code} for match {m_id}")
            return 0
            
        json_data = resp.json()
        
        # Check 2: Did we get a 'Success' field? (1xBet sometimes sends Success: False)
        if not json_data.get("Success", True):
            return 0

        data = json_data.get("Value", {})
        
        # Check 3: Is 'Value' empty?
        if not data:
            # If Value is empty, 1xBet might be blocking this IP's API access
            return 0
            
        rows = []
        
        def collect(groups, period_name, s_id):
            if not groups: return
            for g in groups:
                gid = g.get("groupId")
                # 1xBet API usually wraps events in a nested list: [[event1, event2], [event3]]
                events_container = g.get("events", [])
                for sublist in events_container:
                    # Handle both flat lists and nested lists
                    items = sublist if isinstance(sublist, list) else [sublist]
                    for e in items:
                        if e and e.get('cf'):
                            rows.append({
                                "match_id": int(m_id),
                                "sub_id": int(s_id or m_id),
                                "period": str(period_name),
                                "group_id": int(gid or 0),
                                "raw_data": e,
                                "scraped_at": datetime.now().isoformat()
                            })

        # Process Main Events
        collect(data.get("GE", []), "Full Time", m_id)
        
        # Process Sub Games
        sub_games = data.get("subGamesForMainGame", [])
        for sub in sub_games:
            collect(
                sub.get("eventGroups", []), 
                sub.get("subGameName", "Unknown"), 
                sub.get("id")
            )

        if rows:
            supabase.table("xmatch_odds_deep").insert(rows).execute()
            return len(rows)
        else:
            # If we reached here, 'Value' was found but 'GE' and 'subGames' were empty
            print(f"No markets found in JSON for match {m_id}")
            
    except Exception as e:
        print(f"CRITICAL ERROR on {m_id}: {e}")
    return 0

def run():
    # Let's test with just 5 games first to see the debug prints
    res = supabase.table("xmatch_odds").select("deep_game_id").not_.is_("deep_game_id", "null").limit(5).execute()
    ids = [r['deep_game_id'] for r in res.data]
    
    if not ids:
        print("No deep_game_ids found in xmatch_odds table!")
        return

    print(f"Testing Vacuum on {len(ids)} games...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(vacuum_match, ids))

    print(f"Finished. Total rows added: {sum(results)}")

if __name__ == "__main__":
    run()
