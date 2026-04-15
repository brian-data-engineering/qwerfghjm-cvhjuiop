import os
import yaml
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

PARENT_IDS = ["70292228", "70292226"]
BASE_URL = "https://sh.fn.sportradar.com/betika/en/Etc:UTC/gismo/stats_match_get/"

def get_token():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a real-world context to avoid bot detection
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        # This will store our token once found
        token_container = {"value": None}

        def capture_request(request):
            if "stats_match_get" in request.url and "hmac=" in request.url:
                query_string = request.url.split('?')[1]
                token_container["value"] = query_string
                print(f"Token intercepted!")

        page.on("request", capture_request)

        # Step 1: Visit the main page
        print("Opening Betika Soccer...")
        page.goto("https://www.betika.com/en-ke/s/soccer", wait_until="domcontentloaded")
        
        # Step 2: Active Wait (Wait up to 20s for the token to appear in network)
        for _ in range(20):
            if token_container["value"]:
                break
            time.sleep(1)
        
        browser.close()
        return token_container["value"]

def main():
    token = get_token()
    
    if not token:
        print("FAILED: No token found. Site might be slow or blocking.")
        # Create a dummy file so the GitHub Action doesn't error out on 'ls'
        with open("qw_failed.log", "w") as f:
            f.write(f"Failed to get token at {datetime.now()}")
        return

    print(f"Using Token: {token[:50]}...")

    for pid in PARENT_IDS:
        target_url = f"{BASE_URL}{pid}?{token}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.betika.com/"
        }
        
        try:
            res = requests.get(target_url, headers=headers, timeout=15)
            if res.status_code == 200:
                data = res.json()
                if 'doc' in data and data['doc']:
                    match = data['doc'][0]['data']['match']
                    
                    # qw format
                    qw_data = {
                        'id': pid,
                        'match': f"{match['teams']['home']['name']} vs {match['teams']['away']['name']}",
                        'result': f"{match['result']['home']}-{match['result']['away']}",
                        'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }

                    filename = f"qw_{pid}_{datetime.now().strftime('%H%M%S')}.yml"
                    with open(filename, 'w') as f:
                        yaml.dump(qw_data, f)
                    print(f"Saved: {filename}")
            else:
                print(f"Status {res.status_code} for {pid}")
        except Exception as e:
            print(f"Error on {pid}: {e}")
        
        time.sleep(2)

if __name__ == "__main__":
    main()
