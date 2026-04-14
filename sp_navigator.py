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
        print("🌐 Launching Navigator with Stealth...")
        browser = p.chromium.launch(headless=True)
        # Using a very specific, modern user agent
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # Step 1: Hit the home page first to establish cookies
            print("🏠 Warming up session...")
            page.goto("https://ke.sportpesa.com/", wait_until="networkidle")
            time.sleep(5) 

            # Step 2: Now hit the API
            print(f"📡 Fetching: {NAV_API}")
            page.goto(NAV_API)
            time.sleep(3) # Give it a moment to render the JSON text

            raw_data = page.locator("body").inner_text().strip()

            # Debug: Check if we got the firewall instead of JSON
            if not raw_data or "Challenge" in raw_data or "Access Denied" in raw_data:
                print("🚨 BLOCKED: Hit a firewall/challenge page. Content:")
                print(raw_data[:200]) # See the first 200 chars of the error
                return

            sports_list = json.loads(raw_data)

            for sport in sports_list:
                print(f"🏆 Syncing: {sport['name']}")
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
                        clean_name = str(league["name"]).replace("'", "").replace('"', '')
                        supabase.table("sp_leagues").upsert({
                            "id": league["id"],
                            "country_id": country["id"],
                            "name": clean_name,
                            "top_league_pos": league.get("top_league_pos", 0)
                        }).execute()
            
            print("✅ Lucra Navigation structure updated.")
        except json.JSONDecodeError:
            print("🚨 JSON Error: The API returned something that isn't JSON. Check the logs above.")
        except Exception as e:
            print(f"🚨 Engine Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    sync_navigation()
