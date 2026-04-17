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

def vacuum_match(m_id):
    url = f"https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents"
    params = {
        "cfView": "3", "countEvents": "250", "country": "87", 
        "gameId": str(m_id), "gr": "657", "grMode": "4", 
        "lng": "en", "marketType": "1", "ref": "61"
    }
    
    # These 4 headers are the "secret sauce" to stop getting empty 'Value'
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://1xbet.co.ke/en/line/football/{m_id}",
    }
    
    try:
        resp = session.get(url, params=params, headers=headers, timeout=15)
        
        if resp.status_code != 200: return 0
            
        json_data = resp.json()
        # 1xBet uses lowercase 'value' sometimes, or uppercase 'Value'
        data = json_data.get("Value") or json_data.get("value")
        
        if not data:
            # If we get here, it's still ghosting. Try one more time with a different Ref
            return 0
            
        rows = []
        
        def collect(groups, period_name, s_id):
            if not groups: return
            for g in groups:
                gid = g.get("groupId")
                # Navigate: eventGroups -> events -> [list of events]
                for event_list in g.get("events", []):
                    for e in event_list:
                        if e and e.get('cf'):
                            rows.append({
                                "match_id": int(m_id),
                                "sub_id": int(s_id or m_id),
                                "period": str(period_name),
                                "group_id": int(gid or 0),
                                "raw_data": e,
                                "scraped_at": datetime.now().isoformat()
                            })

        # Process Main
        collect(data.get("GE"), "Full Time", m_id)
        
        # Process SubGames (Corners/Halves)
        sub_games = data.get("subGamesForMainGame") or []
        for sub in sub_games:
            collect(sub.get("eventGroups"), sub.get("subGameName", "Other"), sub.get("id"))

        if rows:
            supabase.table("xmatch_odds_deep").insert(rows).execute()
            return len(rows)
            
    except Exception as e:
        print(f"Error: {e}")
    return 0

# Test run
if __name__ == "__main__":
    # Test with just 2 games to verify the ghosting is gone
    res = supabase.table("xmatch_odds").select("deep_game_id").not_.is_("deep_game_id", "null").limit(2).execute()
    ids = [r['deep_game_id'] for r in res.data]
    print(f"Testing with IDs: {ids}")
    
    for mid in ids:
        count = vacuum_match(mid)
        print(f"Match {mid}: Found {count} markets")
