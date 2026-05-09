import os
import requests
from datetime import datetime, timezone
from supabase import create_client

# --- Config ---
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")

def run_sync():
    print("🚀 Initializing Lucra Live Sync...")
    
    if not URL or not KEY:
        print("❌ ERROR: SUPABASE_URL or SUPABASE_KEY missing from environment.")
        return

    try:
        supabase = create_client(URL, KEY)
        print("🔗 Supabase connection established.")
    except Exception as e:
        print(f"❌ Supabase Client Setup Failed: {e}")
        return

    # 1. WIPE OLD DATA
    try:
        print("🧹 Cleaning old live data...")
        # Using .neq('league_id', 0) is a trick to select all rows for deletion
        supabase.table("xliveleagues").delete().neq("league_id", 0).execute()
        print("✅ Table cleared.")
    except Exception as e:
        print(f"⚠️ Cleanup failed (Table might be empty or missing): {e}")

    # 2. FETCH NEW DATA
    SPORT_IDS = [1, 2, 3, 4, 10]
    base_url = "https://1xbet.co.ke/service-api/LiveFeed/GetSportsShortZip"
    params = "lng=en&country=87&partner=61&virtualSports=false&gr=657&groupChamps=true"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
    }

    all_leagues = []
    BANNED = ["Cyber", "Virtual", "Statistics", "Penalty", "Corner", "Short Football"]

    with requests.Session() as session:
        for s_id in SPORT_IDS:
            url = f"{base_url}?sports={s_id}&{params}"
            print(f"📡 Fetching Sport ID: {s_id}...")
            try:
                resp = session.get(url, headers=headers, timeout=15)
                if resp.status_code != 200:
                    print(f"   ⚠️ HTTP {resp.status_code} for Sport {s_id}")
                    continue
                
                data = resp.json()
                values = data.get("Value", [])
                print(f"   📥 Received {len(values)} items for Sport {s_id}")

                for sport in values:
                    items = sport.get("L", [])
                    for item in items:
                        # Extract nested leagues
                        sub_cats = item.get("SC", [])
                        targets = sub_cats if (sub_cats and isinstance(sub_cats, list)) else [item]

                        for t in targets:
                            l_id = t.get("LI")
                            l_name = t.get("L", "")
                            if l_id and l_name:
                                if any(word.lower() in l_name.lower() for word in BANNED):
                                    continue
                                if l_id < 1000 and " " not in l_name:
                                    continue

                                all_leagues.append({
                                    "league_id": l_id,
                                    "league_name": l_name,
                                    "sport_id": s_id,
                                    "game_count": t.get("GC", 0),
                                    "tier_priority": t.get("T", 0),
                                    "is_top_league": t.get("T", 0) >= 200,
                                    "last_updated": datetime.now(timezone.utc).isoformat()
                                })
            except Exception as e:
                print(f"   ❌ Error on Sport {s_id}: {e}")

    # 3. UPSERT
    if all_leagues:
        # Deduplicate
        unique = {f"{l['sport_id']}_{l['league_id']}": l for l in all_leagues}
        final_list = list(unique.values())
        
        print(f"💾 Attempting to upsert {len(final_list)} leagues...")
        try:
            supabase.table("xliveleagues").upsert(final_list).execute()
            print("✨ Sync Successful!")
        except Exception as e:
            print(f"🚨 Final DB Error: {e}")
    else:
        print("⚠️ No valid leagues found to sync.")

if __name__ == "__main__":
    run_sync()
