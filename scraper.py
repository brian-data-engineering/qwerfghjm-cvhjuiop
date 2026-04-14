import requests
import yaml
import os
import datetime
import re
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
    """Launch headless browser to harvest a fresh Gismo token."""
    print("🌐 Launching browser to harvest token...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    # Head to the stats page
    driver.get("https://statshub.sportradar.com/betika/en")
    
    # Give it a moment to load the scripts
    driver.implicitly_wait(10)
    
    # Sportradar often puts the token in a global JS variable or a script URL
    html = driver.page_source
    driver.quit()
    
    # Regex to find the token pattern: exp=...hmac=...
    match = re.search(r'exp=[^"\'\s]+~hmac=[^"\'\s]+', html)
    if match:
        token = match.group(0)
        print(f"✅ Token Harvested: {token[:20]}...")
        return token
    else:
        raise Exception("❌ Could not find token in page source.")

def fetch_gismo(name, s_id, token):
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
    if not isinstance(item, dict): return None
    m = item.get('match', {})
    if not isinstance(m, dict) or not m: return None
    
    res = m.get('result', {})
    teams = m.get('teams', {})
    
    return {
        'id': m.get('_id'),
        'teams': {'home': teams.get('home', {}).get('name'), 'away': teams.get('away', {}).get('name')},
        'score': {'home': res.get('home', 0), 'away': res.get('away', 0)},
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
        if not data or 'doc' not in data:
            final_output[name] = []
            continue
            
        events = data['doc'][0].get('data', [])
        final_output[name] = [process_match(e) for e in events if process_match(e)]

    with open("results.yaml", "w") as f:
        yaml.dump(final_output, f, default_flow_style=False, sort_keys=False)
    print("🚀 Auto-Sync Complete.")

if __name__ == "__main__":
    main()
