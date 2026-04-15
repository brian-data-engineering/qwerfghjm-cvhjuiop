import os
import yaml
import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright

# The URL from your screenshot
TARGET_URL = "https://statshub.sportradar.com/betika/en/sport/1/tournament/406?date=2026-04-14"
PARENT_IDS = ["70292228", "70292226"]

def scrape_with_interception():
    with sync_playwright() as p:
        # Launching with a real-looking window size
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()

        captured_data = {}

        # This function triggers whenever the browser receives data
        def handle_response(response):
            # We look for the match IDs in the URL of the background requests
            for pid in PARENT_IDS:
                if pid in response.url and "stats_match_get" in response.url:
                    try:
                        print(f"Intercepted data for Match {pid}...")
                        captured_data[pid] = response.json()
                    except:
                        pass

        page.on("response", handle_response)

        print(f"Loading StatsHub...")
        try:
            # Go to the tournament page
            page.goto(TARGET_URL, wait_until="networkidle", timeout=60000)
            
            # Scroll down or wait to trigger the data loads
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(10) # Give the Akamai tokens time to resolve
            
        except Exception as e:
            print(f"Navigation info: {e}")

        # Process whatever we caught
        for pid, json_body in captured_data.items():
            try:
                # Based on your screenshot structure: doc[0] -> data -> match
                doc = json_body.get('doc', [{}])[0]
                match_obj = doc.get('data', {}).get('match')
                
                if match_obj:
                    home = match_obj['teams']['home']['name']
                    away = match_obj['teams']['away']['name']
                    score = f"{match_obj['result'].get('home', 0)}-{match_obj['result'].get('away', 0)}"
                    
                    qw_out = {
                        'id': pid,
                        'teams': f"{home} vs {away}",
                        'score': score,
                        'status': match_obj.get('status', {}).get('name', 'Finished'),
                        'uts': match_obj.get('uts')
                    }

                    filename = f"qw_{pid}.yml"
                    with open(filename, 'w') as f:
                        yaml.dump(qw_out, f, default_flow_style=False)
                    print(f"Saved: {filename}")
            except Exception as parse_err:
                print(f"Failed to parse ID {pid}: {parse_err}")

        browser.close()

if __name__ == "__main__":
    scrape_with_interception()
