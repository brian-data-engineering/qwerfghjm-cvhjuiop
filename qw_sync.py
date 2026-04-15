import os
import yaml
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright
# Import the specific sync function
from playwright_stealth import stealth_sync

PARENT_IDS = ["70292228", "70292226"]
BASE_URL = "https://sh.fn.sportradar.com/betika/en/Etc:UTC/gismo/stats_match_get/"

def get_token():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # CORRECT STEALTH CALL
        try:
            stealth_sync(page)
        except Exception as e:
            print(f"Stealth warning: {e}")

        token_container = {"value": None}

        def capture_request(request):
            if "hmac=" in request.url:
                token_container["value"] = request.url.split('?')[1]

        page.on("request", capture_request)

        print("Opening Betika for handshake...")
        try:
            # We target a direct league page to force the Sportradar widget
            page.goto("https://www.betika.com/en-ke/s/soccer/england/league-one", wait_until="networkidle", timeout=60000)
        except Exception as e:
            print(f"Navigation info: {e}")

        # Wait for token
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
        print("FAILED: No token found.")
        # Create unique error log to avoid git conflicts
        log_name = f"qw_error_{datetime.now().strftime('%H%M%S')}.log"
        with open(log_name, "w") as f:
            f.write(f"Token failure at {datetime.now()}")
        return

    for pid in PARENT_IDS:
        target_url = f"{BASE_URL}{pid}?{token}"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.betika.com/"}
        
        try:
            res = requests.get(target_url, headers=headers, timeout=15)
            if res.status_code == 200:
                data = res.json()
                if 'doc' in data and data['doc']:
                    match = data['doc'][0]['data']['match']
                    qw_output = {
                        'id': pid,
                        'teams': f"{match['teams']['home']['name']} vs {match['teams']['away']['name']}",
                        'result': f"{match['result']['home']}-{match['result']['away']}",
                        'scraped_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    filename = f"qw_{pid}_{datetime.now().strftime('%H%M%S')}.yml"
                    with open(filename, 'w') as f:
                        yaml.dump(qw_output, f, default_flow_style=False)
                    print(f"File created: {filename}")
        except Exception as e:
            print(f"Error on {pid}: {e}")

if __name__ == "__main__":
    main()
