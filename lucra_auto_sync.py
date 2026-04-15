import yaml
import time
from playwright.sync_api import sync_playwright
import requests

# Your target Parent IDs
PARENT_IDS = ["70292228", "70292226"]
BASE_STATS_URL = "https://sh.fn.sportradar.com/betika/en/Etc:UTC/gismo/stats_match_get/"

def get_fresh_token():
    """Starts a browser to 'sniff' the current HMAC token from Sportradar."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        token_found = []

        # Intercept network calls to find the one with the HMAC
        def handle_request(request):
            if "stats_match_get" in request.url and "hmac=" in request.url:
                # Extract everything after the '?'
                token = request.url.split('?')[1]
                token_found.append(token)

        page.on("request", handle_request)
        
        # Visit a generic stats page on Betika to trigger the token generation
        # Replace this with a valid Betika match stats link if needed
        page.goto("https://www.betika.com/en-ke/s/soccer", wait_until="networkidle")
        
        # Small wait to ensure the Gismo stats call happens
        time.sleep(5)
        browser.close()
        
        return token_found[0] if token_found else None

def main():
    print("Step 1: Retrieving fresh HMAC token...")
    token = get_fresh_token()
    
    if not token:
        print("Failed to retrieve token. Ensure the site is accessible.")
        return

    print(f"Token found: {token[:30]}...")
    
    results = []
    headers = {"User-Agent": "Mozilla/5.0...", "Referer": "https://www.betika.com/"}

    for pid in PARENT_IDS:
        print(f"Fetching data for ID: {pid}")
        url = f"{BASE_STATS_URL}{pid}?{token}"
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()['doc'][0]['data']['match']
            results.append({
                'id': pid,
                'teams': f"{data['teams']['home']['name']} vs {data['teams']['away']['name']}",
                'final_score': f"{data['result']['home']}-{data['result']['away']}",
                'status': data['status']['name']
            })
        time.sleep(1)

    with open('lucra_results.yml', 'w') as f:
        yaml.dump({'project': 'Lucra', 'sync_time': time.ctime(), 'matches': results}, f)
    
    print("Done! Check lucra_results.yml")

if __name__ == "__main__":
    main()
