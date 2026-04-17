import os
import requests
import time
from supabase import create_client, Client

# 1. Setup Supabase Connection from Environment
url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")

if not url or not key:
    print("❌ ERROR: SUPABASE_URL or SUPABASE_KEY not found in environment!")
    exit(1)

supabase: Client = create_client(url, key)

def fetch_deep_odds():
    # 2. Get matches from your main table that have a deep_game_id
    # We limit to 50 at a time to stay within GitHub Action time limits
    try:
        response = supabase.table("xmatch_odds") \
            .select("match_id, deep_game_id") \
            .not_.is_("deep_game_id", "null") \
            .order("last_sync", desc=False) \
            .limit(50) \
            .execute()
        
        matches = response.data
    except Exception as e:
        print(f"❌ Failed to fetch matches from Supabase: {e}")
        return

    print(f"🚀 Found {len(matches)} matches to sync.")

    for match in matches:
        m_id = match['match_id']
        d_id = match['deep_game_id']
        
        print(f"🔍 Syncing Match {m_id} (1xBet ID: {d_id})...")
        
        # 3. Hit the 1xBet API
        api_url = f"https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents?gameId={d_id}&lng=en&marketType=1"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        try:
            res = requests.get(api_url, headers=headers, timeout=15)
            
            if res.status_code == 200:
                json_data = res.json()
                
                # Check for content (avoiding 204 "No Content" errors)
                if "subGamesForMainGame" in json_data:
                    # 4. Dump the WHOLE JSON into the new table
                    # Using upsert so we don't duplicate rows for the same match
                    supabase.table("xmatch_odds_deep").upsert({
                        "match_id": m_id,
                        "deep_game_id": d_id,
                        "raw_json": json_data,
                        "scraped_at": "now()"
                    }, on_conflict="match_id").execute()
                    
                    # 5. Update the last_sync time in the main table
                    supabase.table("xmatch_odds").update({"last_sync": "now()"}).eq("match_id", m_id).execute()
                    
                    print(f"✅ Saved deep data for {m_id}")
                else:
                    print(f"⚠️ No deep markets available for {m_id} yet.")
            else:
                print(f"❌ 1xBet returned status {res.status_code} for ID {d_id}")

        except Exception as e:
            print(f"🔥 Error during request for {m_id}: {e}")

        # Respectful delay to avoid IP blocks
        time.sleep(2)

if __name__ == "__main__":
    fetch_deep_odds()
    print("🏁 Deep Sync Workflow Finished.")
