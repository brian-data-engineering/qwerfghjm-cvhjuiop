import requests
import yaml
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
        # Use the base sport hub to trigger the most recent token
        driver.get("https://statshub.sportradar.com/betika/en/sport/1")
        time.sleep(8) 
        
        logs = driver.get_log('performance')
        for entry in logs:
            msg = json.loads(entry['message'])['message']
            if msg.get('method') == 'Network.requestWillBeSent':
                url = msg.get('params', {}).get('request', {}).get('url', '')
                if 'gismo' in url and 'T=' in url:
                    token = re.search(r'T=([^&\s]+)', url).group(1)
                    driver.quit()
                    # Clean potential encoding artifacts
                    return token.replace('\\', '').split('"')[0].split("'")[0]
        driver.quit()
        raise Exception("Token capture failed.")
    except Exception as e:
        if 'driver' in locals(): driver.quit()
        raise e

def parse_match_data(m):
    """Universal parser for match objects found in various Gismo endpoints."""
    if not isinstance(m, dict): return None
    
    # Check if the match is wrapped in an 'event' or 'match' key
    if 'match' in m: m = m['match']
    
    teams = m.get('teams', {})
    home_name = teams.get('home', {}).get('name')
    away_name = teams.get('away', {}).get('name')
    
    if not home_name or not away_name: return None

    # Extraction priority: result block -> ft periods -> p1 periods
    res = m.get('result', {})
    periods = m.get('periods', {})
    ft = periods.get('ft', {})
    
    return {
        'id': m.get('_id'),
        'teams': {
            'home': home_name,
            'away': away_name
        },
        'score': {
            'home': res.get('home', ft.get('home', 0)),
            'away': res.get('away', ft.get('away', 0))
        },
        'status': m.get('matchstatus') or m.get('timeinfo', {}).get('running', 'Unknown'),
        'time': m.get('_dt', {}).get('time', 'Live')
    }

def fetch_results(name, s_id, token):
    """Extracts matches by handling both dict and list structures from Gismo."""
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # We use the 'sport_matches' endpoint as it provides the widest daily coverage
    url = f"https://sh.fn.sportradar.com/betika/en/Etc:UTC/gismo/sport_matches/{s_id}/{date_str}?T={token}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://statshub.sportradar.com/",
        "Origin": "https://statshub.sportradar.com"
    }
    
    matches_found = []
    try:
        r = requests.get(url, headers=headers, timeout=12)
        data = r.json()
        
        doc = data.get('doc', [{}])[0]
        raw_data = doc.get('data', {})

        # CASE 1: Data is a Dictionary (Standard Categorized Feed)
        if isinstance(raw_data, dict):
            for cat_id, cat_info in raw_data.items():
                if not isinstance(cat_info, dict): continue
                for rc in cat_info.get('realcategories', []):
                    for tourn in rc.get('tournaments', []):
                        for m_item in tourn.get('matches', []):
                            processed = parse_match_data(m_item)
                            if processed: matches_found.append(processed)

        # CASE 2: Data is a List (Live Event or Flat Feed)
        elif isinstance(raw_data, list):
            for item in raw_data:
                processed = parse_match_data(item)
                if processed: matches_found.append(processed)

        print(f"📊 {name.capitalize()}: Extracted {len(matches_found)} matches.")
    except Exception as e:
        print(f"⚠️ {name.capitalize()} error: {e}")

    return name, matches_found

def main():
    print("🚀 Starting Lucra Data Sync...")
    try:
        token = get_token()
    except Exception as e:
        print(f"❌ Critical Failure: {e}")
        return

    final_output = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda p: fetch_results(p[0], p[1], token), SPORTS.items()))
    
    for name, matches in results:
        final_output[name] = matches

    # Save to YAML without quotes (as requested for code safety)
    with open("results.yaml", "w") as f:
        yaml.dump(final_output, f, default_flow_style=False, sort_keys=False)
    
    total = sum(len(v) for v in final_output.values())
    print(f"\n✅ Sync Complete. {total} matches saved to results.yaml.")

if __name__ == "__main__":
    main()
