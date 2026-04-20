import os
import requests
import time
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def run_sync():
    # Use a session to maintain cookies and bypass simple bot detection
    session = requests.Session()
    
    base_url = "https://1xbet.co.ke/service-api/LineFeed/GetSportsShortZip"
    # virtualSports=false is safer for technical analysis data
    params = "lng=en&country=87&partner=61&virtualSports=false&gr=657&groupChamps=true"
    
    # Target Sports: 1: Football, 2: Hockey, 3: Basketball, 4: Tennis, 10: Volleyball
    sports_to_fetch = [1, 2, 3, 4, 10]
    
    # Full browser headers to prevent "Expecting value: line 1 column 1 (char 0)"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Referer": "https://1xbet.co.ke/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }

    all_leagues = []

    # Aggressive filter list
    BANNED_KEYWORDS = [
        "statistics", "cyber", "virtual", "special bets", 
        "winner", "extra", "round", "team vs player", 
        "individual", "enhanced", "specials"
    ]

    for sport_id in sports_to_fetch:
        url = f"{base_url}?sports={sport_id}&{params}"
        try:
            print(f"Fetching Sport ID: {sport_id}...")
            response = session.get(url, headers=headers, timeout=20)
            
            if not response.text or response.status_code != 200:
                print(f"Warning: Received empty/invalid response for Sport {sport_id}")
                continue
                
            data = response.json()
            
            for sport_data in data.get("Value", []):
                actual_sport_id = sport_data.get("I")
                
                # Logic: Only grab 'leaf' nodes. 
                # If an item has 'SC' (SubCategories), it is a COUNTRY, not a LEAGUE.
                potential_leagues = []

                # 1. Check direct leagues (like Champions League)
                for item in sport_data.get("L", []):
                    if not item.get("SC"): # No sub-categories means it's a real league
                        potential_leagues.append(item)

                # 2. Check nested leagues (England -> Premier League)
                for country_container in sport_data.get("SC", []):
                    for nested_league in country_container.get("SC", []):
                        potential_leagues.append(nested_league)

                for league in potential_leagues:
                    l_id = league.get("LI")
                    l_name = league.get("L", "")
                    
                    if not l_id or not l_name:
                        continue

                    # Keyword Scrubbing
                    if any(word in l_name.lower() for word in BANNED_KEYWORDS):
                        continue
                    
                    # Tiering and Game count for Lucra prioritization
                    all_leagues.append({
                        "league_id": l_id,
                        "league_name": l_name,
                        "sport_id": actual_sport_id,
                        "game_count": league.get("GC", 0),
                        "tier_priority": league.get("T", 0)
                    })
            
            # Anti-throttling delay
            time.sleep(1.5)

        except Exception as e:
            print(f"Critical error on Sport {sport_id}: {e}")

    # Deduplicate with Sport+League compound key
    unique_leagues = {f"{l['sport_id']}_{l['league_id']}": l for l in all_leagues}
    final_list = list(unique_leagues.values())

    if final_list:
        try:
            # Atomic Upsert
            supabase.table("xsoccerleagues").upsert(final_list).execute()
            print(f"Success! {len(final_list)} verified leagues synced to Lucra.")
            
            # Note: For the 'Nuclear Option' (Stage 3), 
            # run the SQL DELETE via your Supabase Dashboard SQL Editor 
            # or wrap it in a Postgres Function (RPC).
            
        except Exception as e:
            print(f"Supabase Sync Error: {e}")
    else:
        print("No valid leagues found to sync. Check if your IP is temporarily flagged.")

if __name__ == "__main__":
    run_sync()
