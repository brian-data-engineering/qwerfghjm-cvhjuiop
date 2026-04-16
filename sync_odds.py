import os
import requests
import sys
from datetime import datetime
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def get_active_leagues():
    """Fetches leagues with games from the database."""
    res = supabase.table("xsoccerleagues").select("league_id, sport_id").gt("game_count", 0).execute()
    return res.data

def run():
    leagues = get_active_leagues()
    total_leagues = len(leagues)
    print(f"Starting Fast Odds Sync for {total_leagues} leagues...")
    
    # We use a Session to reuse the connection, making it much faster
    session = requests.Session()
    session.headers.update({
        "Referer": "https://1xbet.co.ke/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })

    all_matches = []
    base_url = "https://1xbet.co.ke/service-api/LineFeed/Get1x2_VZip"
    
    for index, league in enumerate(leagues):
        l_id = league['league_id']
        s_id = league['sport_id']
        
        params = f"?sports={s_id}&champs={l_id}&count=1000&lng=en&mode=4&country=87&partner=61&getEmpty=true&virtualSports=true"
        
        try:
            response = session.get(f"{base_url}{params}", timeout=15)
            if response.status_code == 200:
                data = response.json()
                for val in data.get("Value", []):
                    all_matches.append({
                        "match_id": val.get("I"),
                        "league_id": l_id,
                        "sport_id": s_id,
                        "home_team": val.get("O1E"),
                        "away_team": val.get("O2E"),
                        "start_time": datetime.fromtimestamp(val.get("S")).isoformat(),
                        "odds_data": val.get("AE", []),
                        "last_sync": datetime.now().isoformat()
                    })
            
            # PROGRESS TRACKING: This prevents GitHub Actions from looking "stuck"
            if (index + 1) % 50 == 0 or (index + 1) == total_leagues:
                print(f"Progress: {index + 1}/{total_leagues} leagues scanned. Collected {len(all_matches)} matches...")
                sys.stdout.flush() # Force log to show in GitHub immediately

        except Exception as e:
            # Skip failed leagues and keep going
            continue

    # BULK UPSERT: Send to Supabase in chunks of 1000
    if all_matches:
        print(f"Syncing {len(all_matches)} total matches to Supabase...")
        for i in range(0, len(all_matches), 1000):
            chunk = all_matches[i:i + 1000]
            try:
                supabase.table("xmatch_odds").upsert(chunk).execute()
                print(f"Successfully uploaded chunk {i//1000 + 1}")
            except Exception as e:
                print(f"Error uploading chunk: {e}")
    
    print("Lucra Sync Finished.")

if __name__ == "__main__":
    run()
