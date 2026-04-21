import os
import requests
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def is_banned(name, keywords):
    """Helper to check if league name contains banned keywords."""
    return any(word.lower() in name.lower() for word in keywords)

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
        "player total", "points total", "accumulators", "penalty", "corner"
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
                
                items = sport.get("L", [])
                
                for item in items:
                    league_name = item.get("L", "")
                    league_id = item.get("LI")

                    # --- FILTER 1: THE FOLDER CHECK ---
                    # If it has an 'SC' list, it is a container (like 'Germany' or 'England').
                    # We skip the parent and dive into the children.
                    sub_categories = item.get("SC", [])
                    if sub_categories and isinstance(sub_categories, list):
                        for sub in sub_categories:
                            sub_id = sub.get("LI")
                            sub_name = sub.get("L", "")
                            
                            if sub_id and sub_name:
                                if is_banned(sub_name, BANNED_KEYWORDS):
                                    continue
                                    
                                all_leagues.append({
                                    "league_id": sub_id,
                                    "league_name": sub_name,
                                    "sport_id": sport_id,
                                    "game_count": sub.get("GC", 0),
                                    "tier_priority": sub.get("T", 0)
                                })
                        continue # Skip the parent item entirely

                    # --- FILTER 2: STANDALONE LEAGUE VALIDATION ---
                    # If there's no SC list, it's a standalone league.
                    # We still apply a "Folder Protection" rule: 
                    # If ID is small and name has no spaces/dots, it's likely a folder.
                    if league_id and league_name:
                        # Skip if it's a generic country folder that has no sub-categories
                        if league_id < 100 and "." not in league_name and " " not in league_name:
                            continue

                        if is_banned(league_name, BANNED_KEYWORDS):
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
            # Atomic Upsert
            supabase.table("xsoccerleagues").upsert(final_list).execute()
            print(f"Sync Complete: {len(final_list)} valid leagues synced to Lucra.")
        except Exception as e:
            print(f"Database Error: {e}")
    else:
        print("No new leagues found to sync.")

if __name__ == "__main__":
    run_sync()
