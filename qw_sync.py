import os
import yaml
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

# Your Target Parent IDs
PARENT_IDS = ["70292228", "70292226"]
BASE_URL = "https://sh.fn.sportradar.com/betika/en/Etc:UTC/gismo/stats_match_get/"

def get_token():
    """Extracts a fresh HMAC token by mimicking a browser session."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        found_token = []

        # Listen for the specific stats call containing the HMAC
        page.on("request", lambda req: found_token.append(req.url.split('?')[1]) 
                if "stats_match_get" in req.url and "hmac=" in req.url else None)
        
        # Trigger the token generation by visiting the soccer section
        page.goto("https://www.betika.com/en-ke/s/soccer", wait_until="networkidle")
        time.sleep(5) 
        browser.close()
        return found_token[0] if found_token else None

def main():
    token = get_token()
    if not token:
        print("Could not retrieve token.")
        return

    for pid in PARENT_IDS:
        url = f"{BASE_URL}{pid}?{token}"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.betika.com/"}
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            raw_data = response.json()['doc'][0]['data']['match']
            
            # Clean data for Lucra
            result_data = {
                'match_id': pid,
                'teams': f"{raw_data['teams']['home']['name']} vs {raw_data['teams']['away']['name']}",
                'score': f"{raw_data['result']['home']}-{raw_data['result']['away']}",
                'status': raw_data['status']['name'],
                'scraped_at': datetime.now().isoformat()
            }

            # Unique filename: qw_ID_TIMESTAMP.yml
            filename = f"qw_{pid}_{datetime.now().strftime('%H%M%S')}.yml"
            with open(filename, 'w') as f:
                yaml.dump(result_data, f, default_flow_style=False)
            print(f"Created: {filename}")
        
        time.sleep(1)

if __name__ == "__main__":
    main()
