import os
import json
import time
from playwright.sync_api import sync_playwright
from supabase import create_client

# --- CONFIG ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

NAV_API = "https://ke.sportpesa.com/api/navigation"

def sync_navigation():
    with sync_playwright() as p:
        print("🌐 Syncing Navigation Hierarchy...")
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto(NAV_API, wait_until="networkidle")
            raw_data = page.locator("body").inner_text()
            sports_list = json.loads(raw_data)

            for sport in sports_list:
                # 1. Upsert Sport
                supabase.table("sp_sports").upsert({
                    "id": sport["id"],
                    "name": sport["name"],
                    "sort_order": sport["order"]
                }).execute()

                for country in sport.get("countries", []):
                    # 2. Upsert Country
                    supabase.table("sp_countries").upsert({
                        "id": country["id"],
                        "sport_id": sport["id"],
                        "name": country["name"],
                        "iso_name": country["iso_name"]
                    }).execute()

                    for league in country.get("leagues", []):
                        # 3. Upsert League
                        supabase.table("sp_leagues").upsert({
                            "id": league["id"],
                            "country_id": country["id"],
                            "name": league["name"].replace("'", ""), # Clean quotes
                            "top_league_pos": league.get("top_league_pos", 0)
                        }).execute()
            
            print("✅ Navigation structure updated.")
        except Exception as e:
            print(f"🚨 Scraper Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    sync_navigation()
