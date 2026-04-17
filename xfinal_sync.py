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
    # Your verified working URL
    url = "https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents"
    
    params = {
        "cfView": "3", "countEvents": "250", "country": "87",
        "gameId": str(m_id), "gr": "657", "grMode": "4",
        "lng": "en", "marketType": "1", "ref": "61"
    }
    
    # CRITICAL: These headers must match a real browser to avoid 204/529
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://1xbet.co.ke/en/line",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "DNT": "1" # Do Not Track
    }

    try:
        # Use a session to persist the 'human' appearance
        session = requests.Session()
        resp = session.get(url, params=params, headers=headers, timeout=15)

        # STRATEGY: Log failures so you see the 204/529 in your table
        if resp.status_code != 200 or not resp.text or resp.text.strip() == "":
            status = resp.status_code if resp.status_code else "EMPTY"
            supabase.table("xmatch_odds_deep").insert({
                "match_id": int(m_id),
                "period": "SYNC_REJECTED",
                "group_id": 0,
                "raw_data": {"status": status, "reason": "Server returned blank or error"},
                "scraped_at": datetime.now().isoformat()
            }).execute()
            return 0

        data = resp.json().get("Value")
        if not data: return 0

        rows = []
        def collect(groups, period, s_id):
            for g in groups or []:
                gid = g.get("groupId")
                for sublist in g.get("events", []):
                    for e in sublist:
                        if e and e.get('cf'):
                            rows.append({
                                "match_id": int(m_id), "sub_id": int(s_id or m_id),
                                "period": str(period), "group_id": int(gid or 0),
                                "raw_data": e, "scraped_at": datetime.now().isoformat()
                            })

        collect(data.get("GE"), "Full Time", m_id)
        for sub in data.get("subGamesForMainGame", []):
            collect(sub.get("eventGroups"), sub.get("subGameName", "SubGame"), sub.get("id"))

        if rows:
            supabase.table("xmatch_odds_deep").insert(rows).execute()
            return len(rows)

    except Exception as e:
        print(f"ID {m_id} Failed: {e}")
    return 0
