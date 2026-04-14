import os
import json
from playwright.sync_api import sync_playwright
from supabase import create_client

# --- CONFIG ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

NAV_API = "https://ke.sportpesa.com/api/navigation"

def sync_navigation():
    with sync_playwright() as p:
        print("🌐 Launching Navigator...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            page.goto(NAV_API, wait_until="networkidle")
            raw_data = page.locator("body").inner_text()
            sports_list = json.loads(raw_data)

            for sport in sports_list:
                print(f"Syncing Sport: {sport['name']}")
                supabase.table("sp_sports").upsert({
                    "id": sport["id"],
                    "name": sport["name"],
                    "sort_order": sport["order"]
                }).execute()

                for country in sport.get("countries", []):
                    supabase.table("sp_countries").upsert({
                        "id": country["id"],
                        "sport_id": sport["id"],
                        "name": country["name"],
                        "iso_name": country["iso_name"]
                    }).execute()

                    for league in country.get("leagues", []):
                        # Clean quotes as requested
                        clean_name = str(league["name"]).replace("'", "").replace('"', '')
                        supabase.table("sp_leagues").upsert({
                            "id": league["id"],
                            "country_id": country["id"],
                            "name": clean_name,
                            "top_league_pos": league.get("top_league_pos", 0)
                        }).execute()
            
            print("✅ Database hierarchy populated.")
        except Exception as e:
            print(f"🚨 Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    sync_navigation()
