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

session = requests.Session()
session.headers.update({
    "Referer": "https://1xbet.co.ke/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})

def get_active_leagues():
    res = supabase.table("xsoccerleagues").select("league_id, sport_id").gt("game_count", 0).execute()
    return res.data

def fetch_league_matches(league):
    l_id = league['league_id']
    s_id = league['sport_id']
    
    # Keeping your original fast endpoint since we confirmed it has 'CI'
    base_url = "https://1xbet.co.ke/service-api/LineFeed/Get1x2_VZip"
    params = {
        "sports": s_id,
        "champs": l_id,
        "count": 1000,
        "lng": "en",
        "mode": 4,
        "country": 87,
        "partner": 61,
        "getEmpty": "true",
        "virtualSports": "true"
    }
    
    matches = []
    try:
        response = session.get(base_url, params=params, timeout=15)
        if response.status_code == 200:
            data = response.json()
            # 1xbet returns matches in the 'Value' list
            for val in data.get("Value", []):
                match_id = val.get("I")
                start_ts = val.get("S")
                
                if match_id and start_ts:
                    # EXTRACTION FIX: Explicitly grabbing CI from the match object
                    # Based on your JSON sample: "CI": 316263480
                    deep_id = val.get("CI") 
                    
                    # If CI is missing for some reason, we use I as a safety fallback
                    # so the database column is never truly NULL
                    final_deep_id = deep_id if deep_id else match_id
                    
                    matches.append({
                        "match_id": match_id,
                        "deep_game_id": final_deep_id,
                        "league_id": l_id,
                        "sport_id": s_id,
                        "home_team": val.get("O1E"),
                        "away_team": val.get("O2E"),
                        "start_time": datetime.fromtimestamp(start_ts).isoformat(),
                        "last_sync": datetime.now().isoformat()
                    })
    except Exception as e:
        print(f"Error fetching league {l_id}: {e}")
    return matches

def run():
    leagues = get_active_leagues()
    if not leagues:
        print("No active leagues found.")
        return

    print(f"Starting Multi-Threaded Sync for {len(leagues)} leagues...")

    all_matches_raw = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(fetch_league_matches, leagues))
    
    for match_list in results:
        all_matches_raw.extend(match_list)

    if not all_matches_raw:
        print("No matches collected.")
        return

    # De-duplicate
    unique_matches = {m['match_id']: m for m in all_matches_raw}
    final_payload = list(unique_matches.values())
    
    print(f"Syncing {len(final_payload)} unique matches to xmatch_odds...")

    # Bulk Upsert
    for i in range(0, len(final_payload), 1000):
        chunk = final_payload[i:i + 1000]
        try:
            supabase.table("xmatch_odds").upsert(chunk).execute()
            print(f"Chunk {i//1000 + 1} synced.")
        except Exception as e:
            print(f"Upsert error: {e}")
    
    print("Lucra Sync Finished.")

if __name__ == "__main__":
    run()
