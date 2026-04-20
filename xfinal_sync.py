import os
import requests
from supabase import create_client

# 1. Connection
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)

# 2. Hardcoded Match for Testing
m_id = 710135757  # Internal Lucra ID
d_id = 320960634  # 1xBet gameId (from your URL)

def test_sync():
    # This is the exact URL from your browser with ALL parameters
    # Note: Using your specific parameters (country=87, gr=657, etc.)
    api_url = (
        f"https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents?"
        f"cfView=3&countEvents=250&country=87&gameId={d_id}"
        f"&gr=657&grMode=4&lng=en&marketType=1&ref=61"
    )
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    print(f"📡 Fetching: {api_url}")
    
    try:
        response = requests.get(api_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check if the keys we expect exist in the response
            if "subGamesForMainGame" in data:
                print("✅ Found subGamesForMainGame!")
                
                # Upset into the fresh xmatch_odds_deep table
                # Ensure you ran the SQL to create this table first!
                supabase.table("xmatch_odds_deep").upsert({
                    "match_id": m_id,
                    "deep_game_id": d_id,
                    "raw_json": data
                }, on_conflict="match_id").execute()
                
                print(f"🔥 Successfully saved JSON for Inter vs Cagliari.")
            else:
                print("⚠️ JSON returned but 'subGamesForMainGame' key is missing.")
                print(f"Full response keys: {data.keys()}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"🚨 Script Crash: {e}")

if __name__ == "__main__":
    test_sync()
