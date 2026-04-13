import os
import requests
from supabase import create_client, Client
from datetime import datetime

# Stealthily pull from GitHub Secrets
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')

# Initialize the Scout
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Sport IDs for the "Core Four"
SPORTS = [1, 2, 4, 5] 

def fetch_hero_data(sport_id):
    url = f"https://ke.sportpesa.com/api/upcoming/games?sportId={sport_id}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Vibe check failed for Sport {sport_id}: {e}")
        return []

def extract_odds(markets):
    if not markets:
        return None, None, None
    
    selections = markets[0].get('selections', [])
    m1 = next((s['odds'] for s in selections if s['shortName'] == '1'), None)
    mx = next((s['odds'] for s in selections if s['shortName'] == 'X'), None)
    m2 = next((s['odds'] for s in selections if s['shortName'] == '2'), None)
    
    return m1, mx, m2

def run_vibe_check():
    all_heroes = []
    
    for sid in SPORTS:
        data = fetch_hero_data(sid)
        for item in data:
            m1, mx, m2 = extract_odds(item.get('markets', []))
            
            all_heroes.append({
                "game_id": item['id'],
                "sport_id": item['sport']['id'],
                "competition": item['competition']['name'],
                "home_team": item['competitors'][0]['name'],
                "away_team": item['competitors'][1]['name'],
                "match_date": item['date'],
                "market_1": m1,
                "market_x": mx,
                "market_2": m2,
                "last_updated": datetime.now().isoformat()
            })

    if not all_heroes:
        print("No new vibes detected.")
        return

    # Bulk Upsert into Supabase
    # This matches the 'game_id' primary key and updates the odds
    try:
        response = supabase.table("sp_prematch_master").upsert(
            all_heroes, on_conflict="game_id"
        ).execute()
        print(f"Scout successful: {len(all_heroes)} heroes ready for Lucra.")
    except Exception as e:
        print(f"Database sync error: {e}")

if __name__ == "__main__":
    run_vibe_check()
