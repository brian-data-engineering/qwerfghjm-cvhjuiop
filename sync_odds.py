import os
import requests
import sys
import concurrent.futures
from datetime import datetime
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

# Reuse session for connection pooling (vital for speed)
session = requests.Session()
session.headers.update({
    "Referer": "https://1xbet.co.ke/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
})

def get_active_leagues():
    """Fetches leagues with games from the database."""
    res = supabase.table("xsoccerleagues").select("league_id, sport_id").gt("game_count", 0).execute()
    return res.data

def fetch_league_matches(league):
    """Worker function to fetch matches for a single league."""
    l_id = league['league_id']
    s_id = league['sport_id']
    base_url = "https://1xbet.co.ke/service-api/LineFeed/Get1x2_VZip"
    params = f"?sports={s_id}&champs={l_id}&count=1000&lng=en&mode=4&country=87&partner=61&getEmpty=true&virtualSports=true"
    
    matches = []
    try:
        response = session.get(f"{base_url}{params}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            for val in data.get("Value", []):
                # Basic validation to ensure data exists
                if val.get("I") and val.get("S"):
                    matches.append({
                        "match_id": val.get("I"),
                        "league_id": l_id,
                        "sport_id": s_id,
                        "home_team": val.get("O1E"),
                        "away_team": val.get("O2E"),
                        "start_time": datetime.fromtimestamp(val.get("S")).isoformat(),
                        "last_sync": datetime.now().isoformat()
                    })
    except Exception:
        pass
    return matches

def run():
    leagues = get_active_leagues()
    total_leagues = len(leagues)
    print(f"Starting Multi-Threaded Sync for {total_leagues} leagues...")

    all_matches_raw = []
    
    # THE SPEED HACK: 20 Parallel Workers
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(fetch_league_matches, leagues))
    
    # Flatten the list of lists
    for match_list in results:
        all_matches_raw.extend(match_list)

    if not all_matches_raw:
        print("No matches collected. Exiting.")
        return

    # THE DUPLICATE KILLER: Filter by match_id to prevent Supabase 21000 Error
    unique_matches = {}
    for m in all_matches_raw:
        unique_matches[m['match_id']] = m  # Overwrites duplicates with the latest version
    
    final_payload = list(unique_matches.values())
    print(f"Collected {len(all_matches_raw)} total. Unique matches to sync: {len(final_payload)}")

    # BULK UPSERT
    for i in range(0, len(final_payload), 1000):
        chunk = final_payload[i:i + 1000]
        try:
            supabase.table("xmatch_odds").upsert(chunk).execute()
            print(f"Synced chunk {i//1000 + 1} ({len(chunk)} rows)")
        except Exception as e:
            print(f"Error uploading chunk: {e}")
    
    print(f"Lucra Sync Finished. {len(final_payload)} matches now in database.")

if __name__ == "__main__":
    run()
