import os
import requests
from supabase import create_client, Client

# Config
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(URL, KEY)

def run_sync():
    base_url = "https://1xbet.co.ke/service-api/LineFeed/GetSportsShortZip"
    params = "lng=en&country=87&partner=61&virtualSports=false&gr=657&groupChamps=true"
    
    # sports=1 (Football), 2 (Ice Hockey), 3 (Basketball), 4 (Tennis), 10 (Volleyball)
    endpoints = [f"{base_url}?sports={s}&{params}" for s in [1, 2, 3, 4, 10]]
    
    headers = {
        "Referer": "https://1xbet.co.ke/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    all_leagues = []
    BANNED_KEYWORDS = ["statistics", "cyber", "virtual", "special bets", "winner", "extra", "round", "team vs player", "individual", "enhanced"]

    for url in endpoints:
        try:
            response = requests.get(url, headers=headers, timeout=15)
            data = response.json()
            
            for sport in data.get("Value", []):
                sport_id = sport.get("I")
                if not sport_id: continue

                # Deep scan through the structure
                # 1. Check top-level 'L' (Direct leagues like Champions League)
                # 2. Check 'SC' -> 'SC' (Leagues nested inside countries)
                
                potential_items = []
                
                # Add top level items if they don't have sub-categories
                for item in sport.get("L", []):
                    # If an item has GC (Game Count) but NO sub-categories (SC), it's a real league
                    if not item.get("SC"):
                        potential_items.append(item)

                # Drill into countries to get the real leagues
                for country in sport.get("SC", []):
                    for league in country.get("SC", []):
                        potential_items.append(league)

                for item in potential_items:
                    league_id = item.get("LI")
                    league_name = item.get("L", "")
                    
                    if not league_id or not league_name: continue

                    # Strict filtering
                    name_lower = league_name.lower()
                    if any(word in name_lower for word in BANNED_KEYWORDS):
                        continue
                    
                    # Also ignore leagues with very low game counts (optional cleanup)
                    if item.get("GC", 0) == 0:
                        continue

                    all_leagues.append({
                        "league_id": league_id,
                        "league_name": league_name,
                        "sport_id": sport_id,
                        "game_count": item.get("GC", 0),
                        "tier_priority": item.get("T", 0)
                    })

        except Exception as e:
            print(f"Error fetching {url}: {e}")

    # Deduplicate
    unique_leagues = {f"{l['sport_id']}_{l['league_id']}": l for l in all_leagues}
    final_list = list(unique_leagues.values())

    if final_list:
        try:
            supabase.table("xsoccerleagues").upsert(final_list).execute()
            print(f"Sync Complete: {len(final_list)} valid leagues synced.")
        except Exception as e:
            print(f"Database Error: {e}")

if __name__ == "__main__":
    run_sync()
