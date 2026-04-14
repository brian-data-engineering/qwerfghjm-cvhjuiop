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
    """Launch headless browser to harvest a fresh Gismo token from Local Storage or Cookies."""
    print("🌐 Launching browser to harvest token...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        # Head to the stats page
        driver.get("https://statshub.sportradar.com/betika/en")
        
        # Give it a few seconds for the JavaScript to populate Local Storage/Cookies
        time.sleep(10)
        
        # 1. Search Local Storage (Most likely for Gismo)
        storage_data = driver.execute_script("return JSON.stringify(window.localStorage);")
        
        # 2. Search Cookies (Backup)
        cookies = driver.get_cookies()
        cookie_text = "".join([str(c) for c in cookies])
        
        # 3. Search Page Source (Final Fallback)
        html = driver.page_source
        
        combined_data = storage_data + cookie_text + html
        driver.quit()
        
        # Regex to find the token pattern: exp=...hmac=...
        match = re.search(r'exp=[^"\'\s]+~acl=[^"\'\s]+~data=[^"\'\s]+~hmac=[^"\'\s]+', combined_data)
        
        # If the long format fails, try the shorter token format
        if not match:
            match = re.search(r'exp=[^"\'\s]+~hmac=[^"\'\s]+', combined_data)

        if match:
            token = match.group(0)
            # Clean up potential JSON trailing characters
            token = token.replace('\\', '').split('"')[0].split("'")[0]
            print(f"✅ Token Harvested: {token[:40]}...")
            return token
        else:
            raise Exception("❌ Could not find token in Storage, Cookies, or Source.")
            
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
    """Safely extracts data from a match object."""
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
        print(e)
        return

    final_output = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        raw_responses = list(executor.map(lambda p: fetch_gismo(p[0], p[1], token), SPORTS.items()))
        
    for name, data in raw_responses:
        if not data or 'doc' not in data or not data['doc']:
            final_output[name] = []
            continue
            
        events = data['doc'][0].get('data', [])
        # Only process if events is actually a list
        if isinstance(events, list):
            final_output[name] = [process_match(e) for e in events if process_match(e)]
        else:
            final_output[name] = []

    with open("results.yaml", "w") as f:
        yaml.dump(final_output, f, default_flow_style=False, sort_keys=False)
    print("🚀 Auto-Sync Complete.")

if __name__ == "__main__":
    main()
