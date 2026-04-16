import os
import requests
from supabase import create_client, Client

# Initialize Supabase
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def scrape_leagues():
    # The endpoint from your discovery step
    api_url = "https://1xbet.co.ke/service-api/LineFeed/GetSportsShortZip?sports=1&lng=en&country=87&partner=61&virtualSports=true&gr=657&groupChamps=true"
    
    headers = {
        "Referer": "https://1xbet.co.ke/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    response = requests.get(api_url, headers=headers)
    data = response.json()

    league_list = []
    
    # Value[0] contains Football (Sport ID 1)
    sport_data = data.get("Value", [])[0]
    
    # 1. Get Top-Level Leagues (Champions League, World Cup, etc.)
    top_leagues = sport_data.get("L", [])
    
    # 2. Get Country-Specific Leagues (England, Spain, etc.)
    country_groups = sport_data.get("SC", [])

    def format_item(item):
        return {
            "league_id": item.get("LI"),
            "league_name": item.get("L"),
            "sport_id": 1,
            "game_count": item.get("GC", 0),
            "tier_priority": item.get("T", 0)
        }

    # Process both lists
    for item in top_leagues:
        league_list.append(format_item(item))
        
    for country in country_groups:
        for item in country.get("SC", []):
            league_list.append(format_item(item))

    # Clean data: Remove None IDs or "Statistics" leagues to keep Lucra lean
    clean_list = [l for l in league_list if l['league_id'] and "Statistics" not in l['league_name']]

    # Upsert to Supabase
    try:
        result = supabase.table("xsoccerleagues").upsert(clean_list).execute()
        print(f"Successfully synced {len(clean_list)} leagues to xsoccerleagues.")
    except Exception as e:
        print(f"Error pushing to Supabase: {e}")

if __name__ == "__main__":
    scrape_leagues()
