import requests
import json
from datetime import datetime

def vacuum_match(m_id):
    url = "https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents"
    params = {
        "cfView": "3", "countEvents": "250", "country": "87",
        "gameId": str(m_id), "gr": "657", "grMode": "4",
        "lng": "en", "marketType": "1", "ref": "61"
    }
    
    # Headers updated to match your working browser session exactly
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://1xbet.co.ke/en/line"
    }

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            raw_json = resp.json()
            
            # STRATEGY: If 'Value' is missing, check the root for subGames (which you saw in your link)
            data_source = raw_json.get("Value") if raw_json.get("Value") else raw_json
            
            # Look specifically for the keys you confirmed are in the working link
            sub_games = data_source.get("subGamesForMainGame", [])
            main_events = data_source.get("GE", [])

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

            # Capture everything from the structure you provided
            collect(main_events, "Full Time", m_id)
            for sub in sub_games:
                collect(sub.get("eventGroups"), sub.get("subGameName", "SubGame"), sub.get("id"))

            if rows:
                # Insert to Supabase here
                print(f"SUCCESS: Captured {len(rows)} markets for {m_id}")
                return len(rows)
            else:
                print(f"WARNING: No market events found in JSON for {m_id}")
        else:
            print(f"FAILED: Status {resp.status_code}")

    except Exception as e:
        print(f"ERROR: {e}")
    return 0
