import os
import requests
import time
from supabase import create_client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(URL, KEY)

def get_pending_soccer_matches():
    """
    Finds Soccer matches in xmatch_odds that DO NOT have 
    a corresponding entry in xmatch_odds_deep.
    """
    try:
        # 1. Get the list of match_ids that ALREADY have deep odds
        # We only need the IDs to perform a local exclusion
        existing_res = supabase.table("xmatch_odds_deep").select("match_id").execute()
        synced_ids = [r['match_id'] for r in existing_res.data]

        # 2. Fetch Soccer matches from xmatch_odds that have a deep_game_id
        # Limit to 50 or 100 per run to keep it fast and avoid timeouts
        query = supabase.table("xmatch_odds") \
            .select("match_id, deep_game_id, home_team, away_team") \
            .eq("sport_id", 1) \
            .not_.is_("deep_game_id", "null")
        
        # Exclude IDs we already have
        if synced_ids:
            query = query.not_.in_("match_id", synced_ids)

        response = query.limit(100).execute()
        return response.data
    except Exception as e:
        print(f"🚨 Supabase Fetch Error: {e}")
        return []

def run_deep_sync():
    matches = get_pending_soccer_matches()
    
    if not matches:
        print("✅ All soccer matches are already synced.")
        return

    print(f"🚀 Starting sync for {len(matches)} new soccer matches...")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    # Group IDs: 1 (Main), 2 (Handicap), 8 (Totals), 17 (Corners), 19 (Cards)
    ALLOWED_GROUPS = {'1', '2', '8', '17', '19'}

    for match in matches:
        m_id = match['match_id']
        d_id = match['deep_game_id']
        teams = f"{match['home_team']} vs {match['away_team']}"

        # 1xbet Deep Events Endpoint
        api_url = (
            f"https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents?"
            f"cfView=3&countEvents=250&country=87&gameId={d_id}"
            f"&gr=657&grMode=4&lng=en&marketType=1&ref=61"
        )

        try:
            print(f"📡 Requesting: {teams}...")
            response = requests.get(api_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                json_data = response.json()
                
                # Navigate to the events (GE) list inside Value
                val = json_data.get("Value", {})
                all_market_groups = val.get('GE', [])

                if all_market_groups:
                    # Filter for only the groups we want to save space
                    filtered = [
                        group for group in all_market_groups 
                        if str(group.get('G')) in ALLOWED_GROUPS
                    ]

                    # Prepare data for Supabase
                    payload = {
                        "match_id": m_id,
                        "deep_game_id": d_id,
                        "raw_json": {
                            "event_groups": filtered,
                            "last_sync": int(time.time())
                        }
                    }

                    # Upsert into the deep table
                    supabase.table("xmatch_odds_deep").upsert(payload).execute()
                    print(f"✅ Synced: {teams}")
                else:
                    print(f"⚠️ No deep markets found for {teams}")
            
            # 0.8s sleep is usually the "sweet spot" for speed vs anti-ban
            time.sleep(0.8)

        except Exception as e:
            print(f"🚨 Failed on {teams}: {e}")

if __name__ == "__main__":
    run_deep_sync()
