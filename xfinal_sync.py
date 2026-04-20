import os
import requests
import time
from supabase import create_client

# 1. Connection Setup
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)

def get_pending_games():
    """
    Fetches games from xmatch_odds that have a deep_game_id 
    but don't have deep odds in xmatch_odds_deep yet.
    """
    # We use a RPC or a manual filter logic here. 
    # For simplicity, we'll fetch games with deep_game_ids and check 
    # if they need syncing.
    try:
        response = supabase.table("xmatch_odds") \
            .select("match_id, deep_game_id, home_team, away_team") \
            .not_.is_("deep_game_id", "null") \
            .execute()
        return response.data
    except Exception as e:
        print(f"🚨 Error fetching from Supabase: {e}")
        return []

def sync_deep_odds():
    games = get_pending_games()
    print(f"🔄 Found {len(games)} potential games to sync.")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    allowed_groups = ['1', '17', '19', '8', '2']

    for game in games:
        m_id = game['match_id']
        d_id = game['deep_game_id']
        teams = f"{game['home_team']} vs {game['away_team']}"

        api_url = (
            f"https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents?"
            f"cfView=3&countEvents=250&country=87&gameId={d_id}"
            f"&gr=657&grMode=4&lng=en&marketType=1&ref=61"
        )

        print(f"📡 Fetching {teams} (ID: {d_id})...")
        
        try:
            response = requests.get(api_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if "subGamesForMainGame" in data:
                    # --- PRUNING STEP: Save Space for Free Tier ---
                    all_groups = data.get('eventGroups', [])
                    filtered_groups = [
                        g for g in all_groups 
                        if str(g.get('groupId')) in allowed_groups
                    ]
                    
                    # Rebuild a tiny version of the JSON
                    pruned_data = {
                        "eventGroups": filtered_groups,
                        "match_id": m_id # Storing for reference
                    }

                    # --- UPSERT ---
                    supabase.table("xmatch_odds_deep").upsert({
                        "match_id": m_id,
                        "deep_game_id": d_id,
                        "raw_json": pruned_data
                    }, on_conflict="match_id").execute()
                    
                    print(f"✅ Saved & Pruned: {teams}")
                else:
                    print(f"⚠️ No deep data for {teams}")
            
            # Anti-Ban: Don't hit 1xBet too fast
            time.sleep(1.5) 

        except Exception as e:
            print(f"🚨 Failed on {teams}: {e}")

if __name__ == "__main__":
    sync_deep_odds()
