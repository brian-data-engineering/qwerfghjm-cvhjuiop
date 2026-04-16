import os
import requests
from datetime import datetime
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def get_active_leagues():
    """Step 1: Get leagues from our first table that have games"""
    # Only fetch leagues where game_count > 0 to save API calls
    res = supabase.table("xsoccerleagues").select("league_id, sport_id").gt("game_count", 0).execute()
    return res.data

def sync_league_odds(league_id, sport_id):
    """Step 2: Fetch the 'Gold Mine' odds for a specific league"""
    base = "https://1xbet.co.ke/service-api/LineFeed/Get1x2_VZip"
    params = f"?sports={sport_id}&champs={league_id}&count=1000&lng=en&mode=4&country=87&partner=61&getEmpty=true&virtualSports=true"
    
    headers = {
        "Referer": "https://1xbet.co.ke/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(f"{base}{params}", headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
        
        matches = []
        for val in data.get("Value", []):
            matches.append({
                "match_id": val.get("I"),
                "league_id": league_id,
                "sport_id": sport_id,
                "home_team": val.get("O1E"),
                "away_team": val.get("O2E"),
                "start_time": datetime.fromtimestamp(val.get("S")).isoformat(),
                "odds_data": val.get("AE", []), # The deep odds block
                "last_sync": datetime.now().isoformat()
            })

        if matches:
            supabase.table("xmatch_odds").upsert(matches).execute()
            print(f"Synced {len(matches)} matches for League {league_id}")

    except Exception as e:
        print(f"Error on League {league_id}: {e}")

def run():
    leagues = get_active_leagues()
    print(f"Starting Odds Sync for {len(leagues)} leagues...")
    for league in leagues:
        sync_league_odds(league['league_id'], league['sport_id'])

if __name__ == "__main__":
    run()
