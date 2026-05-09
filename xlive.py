import os
import requests
from datetime import datetime
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def is_banned(name, keywords):
    return any(word.lower() in name.lower() for word in keywords)

def run_live_sync():
    session = requests.Session()
    
    # Using LiveFeed endpoint
    base_url = "https://1xbet.co.ke/service-api/LiveFeed/GetSportsShortZip"
    # virtualSports=false to keep Lucra realistic
    params = "lng=en&country=87&partner=61&virtualSports=false&gr=657&groupChamps=true"
    
    endpoints = [
        f"{base_url}?sports=1&{params}",  # Football
        f"{base_url}?sports=2&{params}",  # Ice Hockey
        f"{base_url}?sports=3&{params}",  # Basketball
        f"{base_url}?sports=4&{params}",  # Tennis
        f"{base_url}?sports=10&{params}"  # Volleyball
    ]
    
    headers = {
        "Referer": "https://1xbet.co.ke/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }

    all_leagues = []
    BANNED_KEYWORDS = ["Cyber", "Virtual", "Statistics", "Extra", "Penalty", "Corner", "Short Football"]

    for url in endpoints:
        try:
            response = session.get(url, headers=headers, timeout=20)
            if not response.text.strip(): continue
            data = response.json()
            
            for sport in data.get("Value", []):
                sport_id = sport.get("I")
                items = sport.get("L", [])
                
                for item in items:
                    # Check for nested categories (e.g., England -> Premier League)
                    sub_categories = item.get("SC", [])
                    targets = sub_categories if sub_categories else [item]

                    for target in targets:
                        l_id = target.get("LI")
                        l_name = target.get("L", "")
                        tier = target.get("T", 0)

                        if l_id and l_name and not is_banned(l_name, BANNED_KEYWORDS):
                            # Skip generic folders with no games
                            if l_id < 1000 and " " not in l_name: continue

                            all_leagues.append({
                                "league_id": l_id,
                                "league_name": l_name,
                                "sport_id": sport_id,
                                "game_count": target.get("GC", 0),
                                "tier_priority": tier,
                                "is_top_league": tier >= 200, # Mark major leagues
                                "last_updated": datetime.now().isoformat()
                            })
        except Exception as e:
            print(f"Error: {e}")

    # Deduplicate
    unique_leagues = {f"{l['sport_id']}_{l['league_id']}": l for l in all_leagues}
    final_list = list(unique_leagues.values())

    if final_list:
        try:
            # Targets the NEW xliveleagues table
            supabase.table("xliveleagues").upsert(final_list).execute()
            print(f"Live Sync: {len(final_list)} leagues updated.")
        except Exception as e:
            print(f"DB Error: {e}")

if __name__ == "__main__":
    run_live_sync()
