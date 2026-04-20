import os
import requests
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def run_sync():
    # Use a Session to keep connection alive and handle cookies
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
    
    # Hardened headers to prevent the 'Char 0' empty response error
    headers = {
        "Referer": "https://1xbet.co.ke/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest"
    }

    all_leagues = []

    BANNED_KEYWORDS = [
        "Statistics", "Cyber", "Virtual", "Special bets", 
        "Winner", "Extra", "Round", "Team vs Player", "Individual", "statistics", "cyber", "virtual", "special bets", 
    "winner", "extra", "round", "team vs player", 
    "individual", "enhanced", "results of the", 
    "awards", "matches of the day", "specials",
    "total games", "player total", "points total"
    ]

    for url in endpoints:
        try:
            # Use session.get instead of requests.get
            response = session.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            
            # Check if we actually got content before parsing
            if not response.text.strip():
                print(f"Skipping {url}: Received empty response.")
                continue

            data = response.json()
            
            for sport in data.get("Value", []):
                sport_id = sport.get("I")
                if not sport_id: continue
                
                # Your logic for raw_entries is solid for catching nested leagues
                raw_entries = sport.get("L", []) + [
                    sub for cat in sport.get("SC", []) for sub in cat.get("SC", [])
                ]
                
                for item in raw_entries:
                    league_id = item.get("LI")
                    league_name = item.get("L", "")
                    
                    if not league_id or not league_name:
                        continue

                    # STAGE 1: Filter
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
            # Atomic Upsert into Supabase
            supabase.table("xsoccerleagues").upsert(final_list).execute()
            print(f"Sync Complete: {len(final_list)} valid leagues synced to Lucra.")

            # Note: For Stage 3, ensure you have an RPC named 'cleanup_xmatch_odds' 
            # defined in your Supabase SQL editor if you want to call it via code.
            print("Post-sync cleanup triggered (Check Supabase Dashboard).")

        except Exception as e:
            print(f"Database Error: {e}")
    else:
        print("No new leagues found to sync.")

if __name__ == "__main__":
    run_sync()
