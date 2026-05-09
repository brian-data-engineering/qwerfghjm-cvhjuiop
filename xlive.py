import os
import requests
from datetime import datetime, timezone
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def run_sync():
    try:
        supabase.table("xliveleagues").delete().neq("league_id", 0).execute()
        print("🧹 Table cleared.")
    except Exception as e:
        print(f"Note: Cleanup failed or table empty: {e}")

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate"
    })

    all_leagues = []
    sport_ids = [1, 2, 3, 4, 10]
    BANNED = ["Statistics", "Cyber", "Virtual", "Extra", "Penalty"]

    for s_id in sport_ids:
        url = f"https://1xbet.co.ke/service-api/LiveFeed/GetChampsZip?sport={s_id}&lng=en&country=87&partner=61&virtualSports=true&groupChamps=true"
        
        try:
            response = session.get(url, timeout=20)
            if response.status_code != 200: continue
            
            data = response.json()
            # The root is a dict with a "Value" list
            values = data.get("Value", [])
            
            for item in values:
                # Ensure we are dealing with a dictionary to avoid 'str' error
                if not isinstance(item, dict):
                    continue

                # Check for nested sub-categories (like Israel/Peru folders)
                sub_categories = item.get("SC", [])
                
                if sub_categories and isinstance(sub_categories, list):
                    # It's a folder (like Israel), iterate the actual leagues inside
                    for sub in sub_categories:
                        l_name = sub.get("L", "")
                        if not any(word in l_name for word in BANNED):
                            all_leagues.append({
                                "league_id": sub.get("LI"),
                                "league_name": l_name,
                                "sport_id": sub.get("SI", s_id),
                                "game_count": sub.get("GC", 0),
                                "tier_priority": sub.get("T", 0),
                                "last_updated": datetime.now(timezone.utc).isoformat()
                            })
                else:
                    # It's a standalone league (like Northern Ireland)
                    l_name = item.get("L", "")
                    if not any(word in l_name for word in BANNED):
                        all_leagues.append({
                            "league_id": item.get("LI"),
                            "league_name": l_name,
                            "sport_id": item.get("SI", s_id),
                            "game_count": item.get("GC", 0),
                            "tier_priority": item.get("T", 0),
                            "last_updated": datetime.now(timezone.utc).isoformat()
                        })

        except Exception as e:
            print(f"⚠️ Error parsing Sport {s_id}: {e}")

    if all_leagues:
        # Filter out any entries missing IDs and deduplicate
        valid_leagues = [l for l in all_leagues if l["league_id"] is not None]
        unique_map = {f"{l['sport_id']}_{l['league_id']}": l for l in valid_leagues}
        
        try:
            supabase.table("xliveleagues").upsert(list(unique_map.values())).execute()
            print(f"✨ Success! {len(unique_map)} live leagues synced to Lucra.")
        except Exception as e:
            print(f"🚨 Supabase Error: {e}")
    else:
        print("No leagues found in the response.")

if __name__ == "__main__":
    run_sync()
