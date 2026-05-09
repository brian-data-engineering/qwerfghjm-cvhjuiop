import os
import asyncio
import aiohttp
import requests
from datetime import datetime, timezone
from supabase import create_client

# --- Config ---
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(URL, KEY)

# Sports to track for Lucra Live
SPORT_IDS = [1, 2, 3, 4, 10] 

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json',
    'X-Requested-With': 'XMLHttpRequest'
}

BANNED_KEYWORDS = ["Cyber", "Virtual", "Statistics", "Extra", "Penalty", "Corner", "Short Football"]

def clean_old_live_data():
    """Option A: Wipe the table so only fresh live data exists."""
    try:
        # Deletes all rows where league_id is not 0 (effectively everything)
        supabase.table("xliveleagues").delete().neq("league_id", 0).execute()
        print("🧹 Table xliveleagues cleared for fresh sync.")
    except Exception as e:
        print(f"🚨 Cleanup Error: {e}")

def run_sync():
    # 1. Start with a clean slate
    clean_old_live_data()

    session = requests.Session()
    base_url = "https://1xbet.co.ke/service-api/LiveFeed/GetSportsShortZip"
    params = "lng=en&country=87&partner=61&virtualSports=false&gr=657&groupChamps=true"
    
    all_leagues = []

    for s_id in SPORT_IDS:
        url = f"{base_url}?sports={s_id}&{params}"
        try:
            resp = session.get(url, headers=HEADERS, timeout=15)
            if not resp.text.strip(): continue
            data = resp.json()
            
            for sport in data.get("Value", []):
                sport_id = sport.get("I")
                items = sport.get("L", [])
                
                for item in items:
                    # Dive into nested categories (SC)
                    sub_categories = item.get("SC", [])
                    targets = sub_categories if (sub_categories and isinstance(sub_categories, list)) else [item]

                    for target in targets:
                        l_id = target.get("LI")
                        l_name = target.get("L", "")
                        tier = target.get("T", 0)

                        if l_id and l_name:
                            if any(word.lower() in l_name.lower() for word in BANNED_KEYWORDS):
                                continue
                            
                            # Skip generic country folders with small IDs and no spaces
                            if l_id < 1000 and " " not in l_name:
                                continue

                            all_leagues.append({
                                "league_id": l_id,
                                "league_name": l_name,
                                "sport_id": sport_id,
                                "game_count": target.get("GC", 0),
                                "tier_priority": tier,
                                "is_top_league": tier >= 200,
                                "last_updated": datetime.now(timezone.utc).isoformat()
                            })
        except Exception as e:
            print(f"❌ Error fetching Sport {s_id}: {e}")

    # 2. Deduplicate
    unique_leagues = {f"{l['sport_id']}_{l['league_id']}": l for l in all_leagues}
    final_list = list(unique_leagues.values())

    # 3. Insert fresh data
    if final_list:
        try:
            supabase.table("xliveleagues").upsert(final_list).execute()
            print(f"✅ Live Sync Complete: {len(final_list)} active leagues added to Lucra.")
        except Exception as e:
            print(f"🚨 DB Upsert Error: {e}")
    else:
        print("⚠️ No live leagues found in current feed.")

if __name__ == "__main__":
    run_sync()
