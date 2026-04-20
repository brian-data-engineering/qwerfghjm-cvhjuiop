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
    
    # We focus on the core sports for Lucra
    endpoints = [
        f"{base_url}?sports=1&{params}", # Football
        f"{base_url}?sports=3&{params}", # Basketball
    ]
    
    headers = {
        "Referer": "https://1xbet.co.ke/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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
                
                # 1xBet Structure: Value -> SC (Countries) -> SC (Leagues)
                countries = sport.get("SC", [])
                
                for country in countries:
                    country_name = country.get("L", "") # e.g., "Switzerland"
                    leagues = country.get("SC", [])
                    
                    # If there are no sub-categories, check the top-level L list
                    if not leagues:
                        leagues = country.get("L", []) 

                    for item in leagues:
                        # Skip if it's not a dictionary (1xBet sometimes mixes types)
                        if not isinstance(item, dict): continue
                        
                        league_id = item.get("LI")
                        # Capture the sub-league name (e.g., "Super League")
                        sub_league_name = item.get("L", "") 
                        
                        if not league_id or not sub_league_name:
                            continue

                        # IMPROVEMENT: Combine Country + League Name
                        # This turns "Switzerland" -> "Switzerland. Super League"
                        if country_name and country_name not in sub_league_name:
                            full_league_name = f"{country_name}. {sub_league_name}"
                        else:
                            full_league_name = sub_league_name

                        # Filter Banned Keywords
                        if any(word.lower() in full_league_name.lower() for word in BANNED_KEYWORDS):
                            continue
                        
                        all_leagues.append({
                            "league_id": league_id,
                            "league_name": full_league_name,
                            "sport_id": sport_id,
                            "game_count": item.get("GC", 0),
                            "tier_priority": item.get("T", 0)
                        })

        except Exception as e:
            print(f"Error fetching {url}: {e}")

    # Deduplicate
    unique_leagues = {}
    for l in all_leagues:
        key = f"{l['sport_id']}_{l['league_id']}"
        unique_leagues[key] = l

    final_list = list(unique_leagues.values())

    if final_list:
        try:
            supabase.table("xsoccerleagues").upsert(final_list).execute()
            print(f"Sync Complete: {len(final_list)} detailed leagues synced to Lucra.")
        except Exception as e:
            print(f"Database Error: {e}")
    else:
        print("No new leagues found.")

if __name__ == "__main__":
    run_sync()
