import os
import yaml
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

# Your specific target tournament
TOURNAMENT_URL = "https://statshub.sportradar.com/betika/en/sport/1/tournament/406?date=2026-04-14"
PARENT_IDS = ["70292228", "70292226"]
BASE_API_URL = "https://sh.fn.sportradar.com/betika/en/Etc:UTC/gismo/stats_match_get/"

def get_token():
    with sync_playwright() as p:
        # Launching with specific arguments to bypass basic headless detection
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        token_container = {"value": None}

        # Listener: Specifically looking for the hmac in ANY Sportradar-related API call
        def handle_request(request):
            if "hmac=" in request.url:
                try:
                    # Extract the query string (the part after the ?)
                    token_container["value"] = request.url.split('?')[1]
                    print("SUCCESS: HMAC Token intercepted from network traffic.")
                except Exception:
                    pass

        page.on("request", handle_request)

        print(f"Navigating to Tournament 406 on StatsHub...")
        try:
            # We go to the exact page where the games are listed
            page.goto(TOURNAMENT_URL, wait_until="networkidle", timeout=60000)
            
            # Sometimes the handshake happens a few seconds after the page 'loads'
            for _ in range(10):
                if token_container["value"]:
                    break
                time.sleep(1)
                
        except Exception as e:
            print(f"Navigation note: {e}")

        browser.close()
        return token_container["value"]

def main():
    token = get_token()
    
    if not token:
        print("CRITICAL: No token found. Creating failure log.")
        log_name = f"qw_fail_{datetime.now().strftime('%H%M%S')}.log"
        with open(log_name, "w") as f:
            f.write(f"Failed to find HMAC at {datetime.now()} for Tournament 406")
        return

    # If we have the token, proceed to scrape the specific Match IDs
    for pid in PARENT_IDS:
        full_url = f"{BASE_API_URL}{pid}?{token}"
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://statshub.sportradar.com/"
        }
        
        try:
            response = requests.get(full_url, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if 'doc' in data and data['doc']:
                    match_info = data['doc'][0]['data']['match']
                    
                    qw_result = {
                        'match_id': pid,
                        'tournament': 'Tournament 406',
                        'teams': f"{match_info['teams']['home']['name']} vs {match_info['teams']['away']['name']}",
                        'score': f"{match_info['result']['home']}-{match_info['result']['away']}",
                        'status': match_info['status']['name'],
                        'updated_at': datetime.now().isoformat()
                    }

                    filename = f"qw_data_{pid}.yml"
                    with open(filename, 'w') as f:
                        yaml.dump(qw_result, f, default_flow_style=False)
                    print(f"Scraped Match {pid}: {filename}")
        except Exception as e:
            print(f"Error scraping {pid}: {e}")

if __name__ == "__main__":
    main()
