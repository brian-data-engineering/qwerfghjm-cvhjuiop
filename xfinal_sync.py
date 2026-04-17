import requests
from supabase import create_client

# Config
url_supabase = "YOUR_SUPABASE_URL"
key_supabase = "YOUR_SUPABASE_KEY"
supabase = create_client(url_supabase, key_supabase)

# The target match info
m_id = 710135735
d_id = 320958746

def sync_deep_match(match_id, deep_id):
    # Fetch from 1xBet
    api_url = f"https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents?gameId={deep_id}&lng=en&marketType=1"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    response = requests.get(api_url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        
        # Check if we actually got data or just a 204 shell
        if "subGamesForMainGame" in data:
            # Upsert into Supabase (Update if exists, else Insert)
            supabase.table("xmatch_odds_deep").upsert({
                "match_id": match_id,
                "deep_game_id": deep_id,
                "raw_json": data
            }, on_conflict="match_id").execute()
            print(f"✅ Success: {match_id} fully synced.")
        else:
            print(f"⚠️ Empty: 1xBet has no deep markets for {match_id} yet.")
    else:
        print(f"❌ Error: 1xBet returned status {response.status_code}")

sync_deep_match(m_id, d_id)
