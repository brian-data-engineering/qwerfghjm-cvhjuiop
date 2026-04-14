import os
import json
import yaml
import requests
from supabase import create_client

# --- CONFIG ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

NAV_API = "https://ke.sportpesa.com/api/navigation"

def run_nav_sync():
    headers = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://ke.sportpesa.com/"
    }

    try:
        print(f"📡 Requesting: {NAV_API}")
        response = requests.get(NAV_API, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"🚨 Failed with status: {response.status_code}")
            return

        sports_data = response.json()
        
        yaml_output = []
        batch_sports = []
        batch_countries = []
        batch_leagues = []

        for sport in sports_data:
            sid = sport.get("id")
            sname = sport.get("name")
            
            # 1. Prepare Sport
            batch_sports.append({
                "id": sid,
                "name": sname,
                "sort_order": sport.get("order")
            })

            # 2. Process Countries
            for country in sport.get("countries", []):
                cid = country.get("id")
                batch_countries.append({
                    "id": cid,
                    "sport_id": sid,
                    "name": country.get("name"),
                    "iso_name": country.get("iso_name")
                })

                # 3. Process Leagues
                for league in country.get("leagues", []):
                    # Clean quotes for code safety
                    clean_name = str(league["name"]).replace("'", "").replace('"', '')
                    batch_leagues.append({
                        "id": league.get("id"),
                        "country_id": cid,
                        "name": clean_name,
                        "top_league_pos": league.get("top_league_pos", 0)
                    })
                    
                    # 4. Add to YAML structure
                    yaml_output.append({
                        "sport": sname,
                        "country": country.get("name"),
                        "league": clean_name,
                        "league_id": league.get("id")
                    })

        # --- SAVE YAML ---
        with open("navigation_map.yaml", "w") as f:
            yaml.dump(yaml_output, f, sort_keys=False, default_flow_style=False)
        print("💾 navigation_map.yaml created.")

        # --- SYNC SUPABASE ---
        print("📤 Upserting to Supabase...")
        if batch_sports:
            supabase.table("sp_sports").upsert(batch_sports).execute()
        if batch_countries:
            supabase.table("sp_countries").upsert(batch_countries).execute()
        if batch_leagues:
            supabase.table("sp_leagues").upsert(batch_leagues).execute()
            
        print(f"✅ Success! Synced {len(batch_leagues)} leagues.")

    except Exception as e:
        print(f"🚨 Critical Failure: {e}")

if __name__ == "__main__":
    run_nav_sync()
