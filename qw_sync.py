import os
import yaml
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

# Parent IDs to scrape
PARENT_IDS = ["70292228", "70292226"]
BASE_URL = "https://sh.fn.sportradar.com/betika/en/Etc:UTC/gismo/stats_match_get/"

def get_token():
    with sync_playwright() as p:
        # Launch browser in headless mode
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # Apply stealth to hide bot signatures
        stealth_sync(page)

        token_container = {"value": None}

        # Intercept the HMAC token from the network requests
        def capture_request(request):
            if "hmac=" in request.url:
                query_string = request.url.split('?')[1]
                token_container["value"] = query_string

        page.on("request", capture_request)

        # Visit a specific match page to force the stats engine to load
        print("Opening Betika for stealth handshake...")
        try:
            # We use a direct league link to trigger the Sportradar widget
            page.goto("https://www.betika.com/en-ke/s/soccer/england/league-one", wait_until="networkidle", timeout=60000)
        except:
            print("Navigation reached timeout, checking for intercepted token...")

        # Wait up to 15 seconds for the token to appear
        for _ in range(15):
            if token_container["value"]:
                print("SUCCESS: Token acquired.")
                break
            time.sleep(1)
        
        browser.close()
        return token_container["value"]

def main():
    token = get_token()
    
    if not token:
        print("CRITICAL: No token found. Site is likely blocking the runner.")
        # Create a blank file so the Git step doesn't fail
        with open("qw_empty.txt", "w") as f:
            f.write("Failed to fetch token.")
        return

    for pid in PARENT_IDS:
        target_url = f"{BASE_URL}{pid}?{token}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": "https://www.betika.com/"
        }
        
        try:
            res = requests.get(target_url, headers=headers, timeout=15)
            if res.status_code == 200:
                data = res.json()
                if 'doc' in data and data['doc']:
                    match = data['doc'][0]['data']['match']
                    
                    # qw Unique YAML structure
                    qw_output = {
                        'id': pid,
                        'teams': f"{match['teams']['home']['name']} vs {match['teams']['away']['name']}",
                        'result': f"{match['result']['home']}-{match['result']['away']}",
                        'scraped_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }

                    # Unique filename to prevent overwriting
                    filename = f"qw_{pid}_{datetime.now().strftime('%H%M%S')}.yml"
                    with open(filename, 'w') as f:
                        yaml.dump(qw_output, f, default_flow_style=False)
                    print(f"File created: {filename}")
        except Exception as e:
            print(f"Error processing {pid}: {e}")

if __name__ == "__main__":
    main()
