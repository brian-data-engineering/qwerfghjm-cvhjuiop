import os
import requests
import time
from supabase import create_client

# 1. Connection Setup
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)

def get_pending_soccer_games():
    """
    Fetches only SOCCER (sport_id: 1) games that have a deep_game_id 
    but don't exist in xmatch_odds_deep yet.
    """
    try:
        # Step 1: Get IDs already in deep table to avoid duplicates
        existing = supabase.table("xmatch_odds_deep").select("match_id").execute()
        existing_ids = [item['match_id'] for item in existing.data]

        # Step 2: Fetch only Soccer (sport_id 1) not in the existing list
        query = supabase.table("xmatch_odds") \
            .select("match_id, deep_game_id, home_team, away_team") \
            .eq("sport_id", 1) \
            .not_.is_("deep_game_id", "null")
        
        if existing_ids:
            query = query.not_.in_("match_id", existing_ids)
            
        response = query.limit(100).execute() # Batching for speed/stability
        return response.data
    except Exception as e:
        print(f"🚨 Error fetching from Supabase: {e}")
        return []

def sync_deep_odds():
    games = get_pending_soccer_games()
    
    if not games:
        print("✅ No new soccer games to sync.")
        return

    print(f"🔄 Found {len(games)} new soccer games to sync.")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    # Group IDs: 1 (Main), 2 (Handicap), 8 (Totals), 17 (Corners), 19 (Yellow Cards)
    allowed_groups = ['1', '2', '8', '17', '19']

    for game in games:
        m_id = game['match_id']
        d_id = game['deep_game_id']
        teams = f"{game['home_team']} vs {game['away_team']}"

        # marketType=1 is specifically for Soccer Main Lines
        api_url = (
            f"https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents?"
            f"cfView=3&countEvents=250&country=87&gameId={d_id}"
            f"&gr=657&grMode=4&lng=en&marketType=1&ref=61"
        )

        try:
            # Faster timeout for speed
            response = requests.get(api_url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for value without heavy recursion
                val = data.get("Value", {})
                all_groups = val.get('GE', []) # GE usually contains the market groups
                
                if all_groups:
                    # Faster filtering using set for O(1) lookups
                    allowed_set = set(allowed_groups)
                    filtered_groups = [
                        g for g in all_groups 
                        if str(g.get('G')) in allowed_set
                    ]
                    
                    pruned_data = {
                        "eventGroups": filtered_groups,
                        "match_id": m_id,
                        "last_updated": time.time()
                    }

                    supabase.table("xmatch_odds_deep").upsert({
                        "match_id": m_id,
                        "deep_game_id": d_id,
                        "raw_json": pruned_data
                    }).execute()
                    
                    print(f"⚽ {teams} synced.")
                else:
                    print(f"⚠️ No GE data for {teams}")
            
            # Reduced sleep for faster execution, but keeping 0.5s to avoid IP blocks
            time.sleep(0.5) 

        except Exception as e:
            print(f"🚨 Failed on {teams}: {e}")

if __name__ == "__main__":
    sync_deep_odds()
