import os
import yaml
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth

# Parent IDs to scrape
PARENT_IDS = ["70292228", "70292226"]
BASE_URL = "https://sh.fn.sportradar.com/betika/en/Etc:UTC/gismo/stats_match_get/"

def get_token():
    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # FIXED: Correct stealth call
        stealth(page)

        token_container = {"value": None}

        # Intercept HMAC token from network requests
        def capture_request(request):
            if "hmac=" in request.url:
                query_string = request.url.split('?')[1]
                token_container["value"] = query_string

        page.on("request", capture_request)

        print("Opening Betika for stealth handshake...")
        try:
            # We navigate to the soccer section to trigger the Sportradar handshake
            page.goto("https://www.betika.com/en-ke/s/soccer", wait_until="networkidle", timeout=60000)
        except Exception as e:
            print(f"Navigation info: {e}")

        # Wait up to 20 seconds for the token to appear
        for _ in range(20):
            if token_container["value"]:
                print("SUCCESS: Token acquired.")
                break
            time.sleep(1)
        
        browser.close()
        return token_container["value"]

def main():
    token = get_token()
    
    if not token:
        print("CRITICAL: No token found. Creating log and exiting.")
        with open("qw_error.log", "w") as f:
            f.write(f"Token failure at {datetime.now()}")
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

                    # Unique filename
                    filename = f"qw_{pid}_{datetime.now().strftime('%H%M%S')}.yml"
                    with open(filename, 'w') as f:
                        yaml.dump(qw_output, f, default_flow_style=False)
                    print(f"File created: {filename}")
        except Exception as e:
            print(f"Error processing {pid}: {e}")

if __name__ == "__main__":
    main()
