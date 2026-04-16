import os
import requests
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def run_sync():
    # Endpoints for Football(1), Ice Hockey(2), Basketball(3), Tennis(4), and Table Tennis(10)
    base_url = "https://1xbet.co.ke/service-api/LineFeed/GetSportsShortZip"
    params = "?lng=en&country=87&partner=61&virtualSports=true&gr=657&groupChamps=true"
    
    endpoints = [
        f"{base_url}{params}&sports=1",  # Football
        f"{base_url}{params}&sports=2",  # Ice Hockey
        f"{base_url}{params}&sports=3",  # Basketball
        f"{base_url}{params}&sports=4",  # Tennis
        f"{base_url}{params}&sports=10"  # Table Tennis
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
            
            for sport in data.get("Value", []):
                sport_id = sport.get("I")
                if not sport_id: continue
                
                # 1. Standard Leagues (L)
                for item in sport.get("L", []):
                    if item.get("LI"):
                        all_leagues.append({
                            "league_id": item["LI"],
                            "league_name": item["L"],
                            "sport_id": sport_id,
                            "game_count": item.get("GC", 0),
                            "tier_priority": item.get("T", 0)
                        })
                    
                    # Handle nested Sub-Leagues (common in Tennis/Basketball)
                    for sub in item.get("SC", []):
                        if sub.get("LI"):
                            all_leagues.append({
                                "league_id": sub["LI"],
                                "league_name": sub["L"],
                                "sport_id": sport_id,
                                "game_count": sub.get("GC", 0),
                                "tier_priority": sub.get("T", 0)
                            })

                # 2. Country/Category Leagues (SC)
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

    # Remove duplicates and filter clutter
    # Keeping it simple: filter if 'Statistics' or 'Cyber' is in the name
    unique_leagues = {}
    for l in all_leagues:
        name = l['league_name']
        if not any(word in name for word in ["Statistics", "Cyber", "Virtual"]):
            unique_leagues[l['league_id']] = l

    final_list = list(unique_leagues.values())

    # Supabase Upsert
    if final_list:
        try:
            supabase.table("xsoccerleagues").upsert(final_list).execute()
            print(f"Sync Complete: {len(final_list)} leagues across 5 sports.")
        except Exception as e:
            print(f"Database Error: {e}")

if __name__ == "__main__":
    run_sync()
