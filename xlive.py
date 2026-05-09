import os
import requests
from datetime import datetime, timezone
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def is_banned(name, keywords):
    return any(word.lower() in name.lower() for word in keywords)

def run_sync():
    # --- OPTION A: WIPE TABLE AT START ---
    try:
        supabase.table("xliveleagues").delete().neq("league_id", 0).execute()
        print("🧹 Table cleared for fresh live data.")
    except Exception as e:
        print(f"Cleanup note: {e}")

    session = requests.Session()
    
    # Updated to the LiveFeed URL you provided
    base_url = "https://1xbet.co.ke/service-api/LiveFeed/GetChampsZip"
    params = "lng=en&country=87&partner=61&virtualSports=false&groupChamps=true"
    
    # Sports requested for Lucra
    sport_ids = [1, 2, 3, 4, 10]
    endpoints = [f"{base_url}?sport={s}&{params}" for s in sport_ids]
    
    # CRITICAL: These headers prevent the 406 error
    headers = {
        "Referer": "https://1xbet.co.ke/live",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
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
            # We update session headers to pass the 406 check
            response = session.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            
            data = response.json()
            # The 'LiveFeed' structure uses .get("Value")
            for sport_item in data.get("Value", []):
                sport_id = sport_item.get("I")
                items = sport_item.get("L", [])
                
                for item in items:
                    # Logic from your prematch script (Diving into SC)
                    sub_categories = item.get("SC", [])
                    if sub_categories and isinstance(sub_categories, list):
                        for sub in sub_categories:
                            sub_id = sub.get("LI")
                            sub_name = sub.get("L", "")
                            
                            if sub_id and sub_name and not is_banned(sub_name, BANNED_KEYWORDS):
                                all_leagues.append({
                                    "league_id": sub_id,
                                    "league_name": sub_name,
                                    "sport_id": sport_id,
                                    "game_count": sub.get("GC", 0),
                                    "tier_priority": sub.get("T", 0),
                                    "is_top_league": sub.get("T", 0) >= 200,
                                    "last_updated": datetime.now(timezone.utc).isoformat()
                                })
                        continue 

                    # Standalone League Logic
                    league_id = item.get("LI")
                    league_name = item.get("L", "")
                    if league_id and league_name:
                        # Skip generic folders
                        if league_id < 1000 and " " not in league_name:
                            continue
                        if is_banned(league_name, BANNED_KEYWORDS):
                            continue

                        all_leagues.append({
                            "league_id": league_id,
                            "league_name": league_name,
                            "sport_id": sport_id,
                            "game_count": item.get("GC", 0),
                            "tier_priority": item.get("T", 0),
                            "is_top_league": item.get("T", 0) >= 200,
                            "last_updated": datetime.now(timezone.utc).isoformat()
                        })

        except Exception as e:
            print(f"Error fetching {url}: {e}")

    # Deduplicate (Sport + League)
    unique_leagues = {f"{l['sport_id']}_{l['league_id']}": l for l in all_leagues}
    final_list = list(unique_leagues.values())

    if final_list:
        try:
            supabase.table("xliveleagues").upsert(final_list).execute()
            print(f"✨ Live Sync Complete: {len(final_list)} leagues updated.")
        except Exception as e:
            print(f"Database Error: {e}")
    else:
        print("No live leagues found to sync.")

if __name__ == "__main__":
    run_sync()
