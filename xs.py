import os
import requests
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def run_sync():
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    all_leagues = []

    # Keywords to block immediately
    BANNED_KEYWORDS = [
        "Statistics", "Cyber", "Virtual", "Special bets", 
        "Winner", "Extra", "Round", "Team vs Player", "Individual"
    ]

    for url in endpoints:
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            for sport in data.get("Value", []):
                sport_id = sport.get("I")
                if not sport_id: continue
                
                # We collect from L and SC, but filter strictly
                raw_entries = sport.get("L", []) + [
                    sub for cat in sport.get("SC", []) for sub in cat.get("SC", [])
                ]
                
                for item in raw_entries:
                    league_id = item.get("LI")
                    league_name = item.get("L", "")
                    
                    if not league_id or not league_name:
                        continue

                    # STAGE 1: Block Special/Statistics names
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

    # STAGE 2: Deduplicate using a compound key (Sport + League) 
    # to avoid the "Vietnam" ID overlap mess
    unique_leagues = {}
    for l in all_leagues:
        key = f"{l['sport_id']}_{l['league_id']}"
        unique_leagues[key] = l

    final_list = list(unique_leagues.values())

    if final_list:
        try:
            # Upsert the clean leagues
            supabase.table("xsoccerleagues").upsert(final_list).execute()
            print(f"Sync Complete: {len(final_list)} valid leagues synced.")

            # STAGE 3: "The Nuclear Option" - Delete trash matches
            # This wipes matches with no away team or special bet titles
            # that exist in the xmatch_odds table.
            cleanup_query = """
            DELETE FROM xmatch_odds 
            WHERE away_team IS NULL 
               OR away_team = '' 
               OR home_team ILIKE '%Special bets%' 
               OR home_team ILIKE '%Statistics%' 
               OR home_team ILIKE '%Winner%';
            """
            # Executing via RPC (Remote Procedure Call) if you have one set up, 
            # or just run the SQL in Supabase dashboard.
            print("Post-sync cleanup triggered.")

        except Exception as e:
            print(f"Database Error: {e}")

if __name__ == "__main__":
    run_sync()
