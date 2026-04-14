import requests
import yaml
import os
import datetime
import re
import time
import json
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

SPORTS = {
    "soccer": 1,
    "basketball": 2,
    "tennis": 5,
    "ice_hockey": 4,
    "table_tennis": 20
}

def get_token():
    """Captures the T= token by listening and interacting with the page."""
    print("🌐 Launching browser to capture network logs...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Enable performance logging to sniff background API traffic
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        driver.get("https://statshub.sportradar.com/betika/en")
        
        # 1. INTERACTION: Scroll to trigger calls
        for i in range(3):
            driver.execute_script(f"window.scrollTo(0, {i * 400});")
            time.sleep(3)
        
        # 2. RETRY LOOP: Check logs incrementally
        max_attempts = 5
        found_urls = [] # For debugging

        for attempt in range(max_attempts):
            print(f"🔍 Scan {attempt + 1}/{max_attempts} for background requests...")
            logs = driver.get_log('performance')
            
            for entry in logs:
                msg_json = json.loads(entry['message'])
                message = msg_json.get('message', {})
                
                if message.get('method') == 'Network.requestWillBeSent':
                    url = message.get('params', {}).get('request', {}).get('url', '')
                    
                    # LOGGING: Print all background API/XHR calls found
                    if any(x in url for x in ['gismo', 'sportradar', 'betika']):
                        if url not in found_urls:
                            # Show a shortened version of the URL in the console
                            print(f"   📡 Found: {url[:80]}...")
                            found_urls.append(url)

                    # TARGET: Find the token
                    if 'gismo' in url and 'T=' in url:
                        match = re.search(r'T=([^&\s]+)', url)
                        if match:
                            token = match.group(1)
                            token = token.replace('\\', '').split('"')[0].split("'")[0]
                            driver.quit()
                            print(f"\n✅ Token Captured: {token[:40]}...")
                            return token
            
            time.sleep(5) 

        driver.quit()
        # If we get here, show what we found for debugging
        print("\n❌ Failed. Summary of relevant requests found:")
        for u in found_urls:
            print(f"  - {u[:100]}")
            
        raise Exception("❌ No Gismo request with 'T=' appeared in network logs.")
            
    except Exception as e:
        if 'driver' in locals():
            driver.quit()
        raise e

def fetch_gismo(name, s_id, token):
    """Hits the main stats endpoint for the day."""
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    url = f"https://sh.fn.sportradar.com/betika/en/Etc:UTC/gismo/stats_sport_matches_prevnext/{s_id}/{date_str}/0?T={token}"
    headers = {
        "Referer": "https://statshub.sportradar.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        r = requests.get(url, headers=headers, timeout=15)
        return name, r.json()
    except:
        return name, None

def process_match(item):
    """Safely extracts match data, ignoring strings/metadata in the list."""
    if not isinstance(item, dict): return None
    m = item.get('match', {})
    if not isinstance(m, dict) or not m: return None
    
    res = m.get('result', {})
    teams = m.get('teams', {})
    
    return {
        'id': m.get('_id'),
        'teams': {
            'home': teams.get('home', {}).get('name'), 
            'away': teams.get('away', {}).get('name')
        },
        'score': {
            'home': res.get('home', 0), 
            'away': res.get('away', 0)
        },
        'status': m.get('matchstatus'),
        'time': m.get('_dt', {}).get('time')
    }

def main():
    try:
        token = get_token()
    except Exception as e:
        print(f"Failed to harvest token: {e}")
        return

    final_output = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        raw_responses = list(executor.map(lambda p: fetch_gismo(p[0], p[1], token), SPORTS.items()))
        
    for name, data in raw_responses:
        if not data or 'doc' not in data or not data['doc']:
            final_output[name] = []
            continue
            
        events = data['doc'][0].get('data', [])
        
        if isinstance(events, list):
            final_output[name] = [process_match(e) for e in events if process_match(e)]
        else:
            final_output[name] = []

    # Save as clean YAML
    with open("results.yaml", "w") as f:
        yaml.dump(final_output, f, default_flow_style=False, sort_keys=False)
    
    print("🚀 Auto-Sync Complete. results.yaml updated.")

if __name__ == "__main__":
    main()
