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
    # --- Wipe Table First ---
    try:
        supabase.table("xliveleagues").delete().neq("league_id", 0).execute()
        print("🧹 Table cleared.")
    except Exception as e:
        print(f"Cleanup note: {e}")

    # Use a session to persist cookies and headers like a browser
    session = requests.Session()
    
    # EXACT URL structure from your working link
    # We will loop through the sport IDs and inject them into the 'sport=' parameter
    sport_ids = [1, 2, 3, 4, 10]
    
    # The absolute mirror of what works in your browser
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
    BANNED_KEYWORDS = ["Statistics", "Cyber", "Virtual", "Special bets", "Extra", "Penalty", "Corner"]

    for s_id in sport_ids:
        # CONSTRUCTED EXACTLY LIKE YOUR WORKING LINK
        url = f"https://1xbet.co.ke/service-api/LiveFeed/GetChampsZip?sport={s_id}&lng=en&country=87&partner=61&virtualSports=true&groupChamps=true"
        
        try:
            # We don't use stream=True because Zip endpoints are usually small/compressed
            response = session.get(url, headers=headers, timeout=20)
            
            if response.status_code == 406:
                print(f"❌ Sport {s_id}: 406 Not Acceptable. The server is still rejecting the header handshake.")
                continue
                
            response.raise_for_status()
            data = response.json()
            
            # Process the "Value" array
            for sport_item in data.get("Value", []):
                actual_sport_id = sport_item.get("I")
                items = sport_item.get("L", [])
                
                for item in items:
                    # Check for nested leagues (SC)
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
                        # Folder protection
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

    # Deduplicate and Upsert
    if all_leagues:
        unique = {f"{l['sport_id']}_{l['league_id']}": l for l in all_leagues}
        final_list = list(unique.values())
        try:
            supabase.table("xliveleagues").upsert(final_list).execute()
            print(f"✨ Successfully synced {len(final_list)} live leagues to Lucra.")
        except Exception as e:
            print(f"🚨 Supabase Error: {e}")
    else:
        print("No live leagues found. Ensure the working links are returning data at this moment.")

if __name__ == "__main__":
    run_sync()
