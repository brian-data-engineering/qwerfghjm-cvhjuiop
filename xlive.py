import os
import requests
from datetime import datetime, timezone
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def run_sync():
    # 1. Clear the table
    supabase.table("xliveleagues").delete().neq("league_id", 0).execute()
    print("🧹 Table cleared.")

    session = requests.Session()
    
    # These headers are the "secret sauce" to stop the empty response/406 errors
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",  # Tells server to send readable compressed data
        "Referer": "https://1xbet.co.ke/en/live",
        "X-Requested-With": "XMLHttpRequest",
        "Connection": "keep-alive"
    })

    all_leagues = []
    sport_ids = [1, 2, 3, 4, 10]

    for s_id in sport_ids:
        # CONSTRUCTING YOUR EXACT LINK
        target_url = f"https://1xbet.co.ke/service-api/LiveFeed/GetChampsZip?sport={s_id}&lng=en&country=87&partner=61&virtualSports=true&groupChamps=true"
        
        try:
            response = session.get(target_url, timeout=20)
            
            if response.status_code != 200:
                print(f"❌ Sport {s_id} failed with Status: {response.status_code}")
                continue

            # This prevents the "char 0" error
            if not response.text.strip():
                print(f"⚠️ Sport {s_id} returned an empty body.")
                continue

            data = response.json()
            
            # Parsing logic for the JSON structure you provided
            for sport_item in data.get("Value", []):
                # The JSON uses 'I' for ID or 'SI' for Sport ID
                actual_s_id = sport_item.get("I", s_id)
                leagues_list = sport_item.get("L", [])
                
                for league in leagues_list:
                    # Dive into sub-categories (SC) if they exist
                    sub_cats = league.get("SC", [])
                    if sub_cats:
                        for sub in sub_cats:
                            all_leagues.append({
                                "league_id": sub.get("LI"),
                                "league_name": sub.get("L"),
                                "sport_id": actual_s_id,
                                "game_count": sub.get("GC", 0),
                                "tier_priority": sub.get("T", 0)
                            })
                    else:
                        # Standalone league
                        all_leagues.append({
                            "league_id": league.get("LI"),
                            "league_name": league.get("L"),
                            "sport_id": actual_s_id,
                            "game_count": league.get("GC", 0),
                            "tier_priority": league.get("T", 0)
                        })

        except Exception as e:
            print(f"⚠️ Error on Sport {s_id}: {e}")

    if all_leagues:
        # Deduplicate and Upsert
        unique_data = {f"{item['sport_id']}_{item['league_id']}": item for item in all_leagues if item['league_id']}.values()
        supabase.table("xliveleagues").upsert(list(unique_data)).execute()
        print(f"✨ Success! Synced {len(unique_data)} live leagues.")
    else:
        print("No leagues parsed. Check the logs above for status codes.")

if __name__ == "__main__":
    run_sync()
