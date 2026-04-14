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
    """Captures the T= token by listening to background network traffic (CDP)."""
    print("🌐 Launching browser to capture network logs...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Enable performance logging to sniff network requests
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        # Navigate to the main stats page
        driver.get("https://statshub.sportradar.com/betika/en")
        
        # Wait for the background XHR/Gismo calls to fire (12 seconds for slow runners)
        time.sleep(12)
        
        # Pull performance logs
        logs = driver.get_log('performance')
        driver.quit()
        
        print(f"🔍 Analyzing {len(logs)} network events...")
        
        for entry in logs:
            message = json.loads(entry['message'])['message']
            
            # Filter for events where a request was sent
            if message.get('method') == 'Network.requestWillBeSent':
                url = message.get('params', {}).get('request', {}).get('url', '')
                
                # Sniff for the Gismo endpoint containing the T parameter
                if 'gismo' in url and 'T=' in url:
                    match = re.search(r'T=([^&\s]+)', url)
                    if match:
                        token = match.group(1)
                        # Clean up any potential encoding or quotes
                        token = token.replace('\\', '').split('"')[0].split("'")[0]
                        print(f"✅ Token Captured: {token[:40]}...")
                        return token
        
        raise Exception("❌ Network logs checked, but no Gismo request with a token was found.")
            
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
    """Safely extracts data from a match object, avoiding metadata strings."""
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
    # Use 5 threads to fetch all sports simultaneously
    with ThreadPoolExecutor(max_workers=5) as executor:
        raw_responses = list(executor.map(lambda p: fetch_gismo(p[0], p[1], token), SPORTS.items()))
        
    for name, data in raw_responses:
        if not data or 'doc' not in data or not data['doc']:
            final_output[name] = []
            continue
            
        events = data['doc'][0].get('data', [])
        
        if isinstance(events, list):
            # process_match will return None for non-match items, which we filter out here
            final_output[name] = [process_match(e) for e in events if process_match(e)]
        else:
            final_output[name] = []

    # Write results to YAML (Lucra project format)
    with open("results.yaml", "w") as f:
        yaml.dump(final_output, f, default_flow_style=False, sort_keys=False)
    
    print("🚀 Auto-Sync Complete. results.yaml updated.")

if __name__ == "__main__":
    main()
