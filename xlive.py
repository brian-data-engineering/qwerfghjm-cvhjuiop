import os
import requests
from datetime import datetime, timezone
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def is_banned(name, keywords):
    return any(word.lower() in name.lower() for word in keywords)

def run_sync():
    try:
        supabase.table("xliveleagues").delete().neq("league_id", 0).execute()
        print("🧹 Table cleared.")
    except Exception as e:
        print(f"Cleanup note: {e}")

    session = requests.Session()
    
    # EXACT headers to handle the "Zip" encoding and avoid empty/406 responses
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Host": "1xbet.co.ke",
        "Referer": "https://1xbet.co.ke/en/live",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }

    all_leagues = []
    sport_ids = [1, 2, 3, 4, 10]
    BANNED_KEYWORDS = ["Statistics", "Cyber", "Virtual", "Special bets", "Extra", "Penalty", "Corner"]

    for s_id in sport_ids:
        url = f"https://1xbet.co.ke/service-api/LiveFeed/GetChampsZip?sport={s_id}&lng=en&country=87&partner=61&virtualSports=true&groupChamps=true"
        
        try:
            response = session.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            # Check if content is actually there before parsing
            if not response.content:
                print(f"⚠️ Sport {s_id}: Received empty response.")
                continue

            data = response.json()
            
            # Navigate the "Value" array from your JSON sample
            for sport_item in data.get("Value", []):
                actual_sport_id = sport_item.get("SI") or s_id
                items = sport_item.get("L", []) if "L" in sport_item else [sport_item]
                
                # If 'L' is not present, the sport_item itself might be the league
                if not isinstance(items, list): items = [sport_item]

                for item in items:
                    # SC Diving (For folders like Italy, Spain)
                    sub_cats = item.get("SC", [])
                    if sub_cats and isinstance(sub_cats, list):
                        for sub in sub_cats:
                            l_id = sub.get("LI")
                            l_name = sub.get("L", "")
                            if l_id and l_name and not is_banned(l_name, BANNED_KEYWORDS):
                                all_leagues.append({
                                    "league_id": l_id,
                                    "league_name": l_name,
                                    "sport_id": actual_sport_id,
                                    "game_count": sub.get("GC", 0),
                                    "tier_priority": sub.get("T", 0),
                                    "is_top_league": sub.get("T", 0) >= 200,
                                    "last_updated": datetime.now(timezone.utc).isoformat()
                                })
                        continue

                    # Standalone league
                    l_id = item.get("LI")
                    l_name = item.get("L", "")
                    if l_id and l_name and not is_banned(l_name, BANNED_KEYWORDS):
                        if l_id < 1000 and " " not in l_name:
                            continue

                        all_leagues.append({
                            "league_id": l_id,
                            "league_name": l_name,
                            "sport_id": actual_sport_id,
                            "game_count": item.get("GC", 0),
                            "tier_priority": item.get("T", 0),
                            "is_top_league": item.get("T", 0) >= 200,
                            "last_updated": datetime.now(timezone.utc).isoformat()
                        })

        except Exception as e:
            print(f"⚠️ Error on Sport {s_id}: {e}")

    if all_leagues:
        # Deduplicate
        unique = {f"{l['sport_id']}_{l['league_id']}": l for l in all_leagues}
        final_list = list(unique.values())
        try:
            supabase.table("xliveleagues").upsert(final_list).execute()
            print(f"✨ Success: {len(final_list)} live leagues synced to Lucra.")
        except Exception as e:
            print(f"🚨 Supabase Error: {e}")
    else:
        print("No live leagues found.")

if __name__ == "__main__":
    run_sync()
