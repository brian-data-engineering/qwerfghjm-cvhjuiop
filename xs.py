import os
import requests
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def run_sync():
    # List of endpoints to scrape (Football and Tennis)
    endpoints = [
        "https://1xbet.co.ke/service-api/LineFeed/GetSportsShortZip?sports=1&lng=en&country=87&partner=61&virtualSports=true&gr=657&groupChamps=true",
        "https://1xbet.co.ke/service-api/LineFeed/GetSportsShortZip?sports=4&lng=en&country=87&partner=61&virtualSports=true&gr=657&groupChamps=true"
    ]
    
    headers = {
        "Referer": "https://1xbet.co.ke/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    all_leagues = []

    for url in endpoints:
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            # Value is a list of sports
            for sport in data.get("Value", []):
                sport_id = sport.get("I")
                
                # 1. Process top-level list (L)
                for top_league in sport.get("L", []):
                    if top_league.get("LI"):
                        all_leagues.append({
                            "league_id": top_league["LI"],
                            "league_name": top_league["L"],
                            "sport_id": sport_id,
                            "game_count": top_league.get("GC", 0),
                            "tier_priority": top_league.get("T", 0)
                        })
                    
                    # Some Tennis entries (like ATP/WTA) have sub-leagues inside 'SC'
                    for sub in top_league.get("SC", []):
                        if sub.get("LI"):
                            all_leagues.append({
                                "league_id": sub["LI"],
                                "league_name": sub["L"],
                                "sport_id": sport_id,
                                "game_count": sub.get("GC", 0),
                                "tier_priority": sub.get("T", 0)
                            })

                # 2. Process nested country/category list (SC)
                for category in sport.get("SC", []):
                    for league in category.get("SC", []):
                        if league.get("LI"):
                            all_leagues.append({
                                "league_id": league["LI"],
                                "league_name": league["L"],
                                "sport_id": sport_id,
                                "game_count": league.get("GC", 0),
                                "tier_priority": league.get("T", 0)
                            })

        except Exception as e:
            print(f"Error fetching {url}: {e}")

    # Remove duplicates by ID and filter out unwanted strings
    unique_leagues = {l['league_id']: l for l in all_leagues if "Statistics" not in l['league_name']}.values()
    final_list = list(unique_leagues)

    # Supabase Upsert
    if final_list:
        try:
            supabase.table("xsoccerleagues").upsert(final_list).execute()
            print(f"Successfully synced {len(final_list)} items (Football & Tennis).")
        except Exception as e:
            print(f"Database Error: {e}")

if __name__ == "__main__":
    run_sync()
