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
    """Captures the T= token via stealth headless browser."""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    try:
        driver.get("https://statshub.sportradar.com/betika/en/sport/1")
        time.sleep(10) # Give it time to fire requests
        
        logs = driver.get_log('performance')
        for entry in logs:
            msg = json.loads(entry['message'])['message']
            if msg.get('method') == 'Network.requestWillBeSent':
                url = msg.get('params', {}).get('request', {}).get('url', '')
                if 'gismo' in url and 'T=' in url:
                    token = re.search(r'T=([^&\s]+)', url).group(1)
                    driver.quit()
                    return token.replace('\\', '').split('"')[0].split("'")[0]
        driver.quit()
        raise Exception("Token capture failed.")
    except Exception as e:
        if 'driver' in locals(): driver.quit()
        raise e

def process_match(m):
    """Direct extraction of match results."""
    res = m.get('result', {})
    teams = m.get('teams', {})
    # Return None if names are missing (filters out ghost entries)
    if not teams.get('home', {}).get('name'): return None

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

def fetch_results(name, s_id, token):
    """Fetches and flattens match data from the Gismo API."""
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    url = f"https://sh.fn.sportradar.com/betika/en/Etc:UTC/gismo/sport_matches/{s_id}/{date_str}?T={token}"
    
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        matches_found = []
        
        # Navigate the Gismo nesting: doc -> data -> categories -> realcategories -> tournaments -> matches
        categories = data.get('doc', [{}])[0].get('data', {})
        for cat_id in categories:
            real_cats = categories[cat_id].get('realcategories', [])
            for rc in real_cats:
                for tourn in rc.get('tournaments', []):
                    for match in tourn.get('matches', []):
                        m_data = process_match(match)
                        if m_data: matches_found.append(m_data)
        
        print(f"📊 {name.capitalize()}: {len(matches_found)} matches found.")
        return name, matches_found
    except:
        return name, []

def main():
    print("🚀 Starting sync...")
    token = get_token()
    final_output = {}

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda p: fetch_results(p[0], p[1], token), SPORTS.items()))
    
    for name, matches in results:
        final_output[name] = matches

    with open("results.yaml", "w") as f:
        yaml.dump(final_output, f, default_flow_style=False, sort_keys=False)
    
    total = sum(len(v) for v in final_output.values())
    print(f"✅ Success! results.yaml updated with {total} matches.")

if __name__ == "__main__":
    main()
