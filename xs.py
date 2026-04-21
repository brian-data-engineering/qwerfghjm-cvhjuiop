import os
import requests
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def run_sync():
    session = requests.Session()
    
    base_url = "https://1xbet.co.ke/service-api/LineFeed/GetSportsShortZip"
    params = "lng=en&country=87&partner=61&virtualSports=true&gr=657&groupChamps=true"
    
    endpoints = [
        f"{base_url}?sports=1&{params}",
        f"{base_url}?sports=2&{params}",
        f"{base_url}?sports=3&{params}",
        f"{base_url}?sports=4&{params}",
        f"{base_url}?sports=10&{params}"
    ]
    
    headers = {
        "Referer": "https://1xbet.co.ke/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest"
    }

    all_leagues = []

    BANNED_KEYWORDS = [
        "Statistics", "Cyber", "Virtual", "Special bets", "Winner", "Extra", 
        "Round", "Team vs Player", "Individual", "enhanced", "results of the", 
        "awards", "matches of the day", "specials", "total games", 
        "player total", "points total", "accumulators"
    ]

    for url in endpoints:
        try:
            response = session.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            
            if not response.text.strip():
                continue

            data = response.json()
            
            for sport in data.get("Value", []):
                sport_id = sport.get("I")
                if not sport_id: continue
                
                # The top-level L list contains both standalone leagues and country folders
                items = sport.get("L", [])
                
                for item in items:
                    # Check if this is a "Folder" (like England, Germany, etc.)
                    # They have a 'CSC' count and an 'SC' list
                    if "SC" in item and isinstance(item["SC"], list) and len(item["SC"]) > 0:
                        for sub_league in item["SC"]:
                            league_id = sub_league.get("LI")
                            league_name = sub_league.get("L", "")
                            
                            if league_id and league_name:
                                # Stage 1: Filter
                                if any(word.lower() in league_name.lower() for word in BANNED_KEYWORDS):
                                    continue
                                    
                                all_leagues.append({
                                    "league_id": league_id,
                                    "league_name": league_name,
                                    "sport_id": sport_id,
                                    "game_count": sub_league.get("GC", 0),
                                    "tier_priority": sub_league.get("T", 0)
                                })
                    else:
                        # It's a standalone league (like World Cup or Champions League)
                        league_id = item.get("LI")
                        league_name = item.get("L", "")
                        
                        if league_id and league_name:
                            if any(word.lower() in league_name.lower() for word in BANNED_KEYWORDS):
                                continue
                                
                            all_leagues.append({
                                "league_id": league_id,
                                "league_name": league_name,
                                "sport_id": sport_id,
                                "game_count": item.get("GC", 0),
                                "tier_priority": item.get("T", 0)
                            })

        except Exception as e:
            print(f"Error fetching {url}: {e}")

    # STAGE 2: Deduplicate (Sport + League)
    unique_leagues = {}
    for l in all_leagues:
        key = f"{l['sport_id']}_{l['league_id']}"
        unique_leagues[key] = l

    final_list = list(unique_leagues.values())

    if final_list:
        try:
            supabase.table("xsoccerleagues").upsert(final_list).execute()
            print(f"Sync Complete: {len(final_list)} valid leagues synced to Lucra.")
        except Exception as e:
            print(f"Database Error: {e}")
    else:
        print("No new leagues found to sync.")

if __name__ == "__main__":
    run_sync()
