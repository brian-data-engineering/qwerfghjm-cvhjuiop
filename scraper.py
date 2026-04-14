import requests
import yaml
import os
import datetime
from concurrent.futures import ThreadPoolExecutor

# Your target Sports IDs
SPORTS = {
    "soccer": 1,
    "basketball": 2,
    "tennis": 5,
    "ice_hockey": 4,
    "table_tennis": 20
}

# CONFIGURATION
TOKEN = os.getenv("SPORTRADAR_TOKEN")
# Gismo requires the Referer header to match the site you're scraping
HEADERS = {
    "Referer": "https://statshub.sportradar.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_gismo(name, s_id):
    """Hits the main stats endpoint for the day."""
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    url = f"https://sh.fn.sportradar.com/betika/en/Etc:UTC/gismo/stats_sport_matches_prevnext/{s_id}/{date_str}/0?T={TOKEN}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        return name, r.json()
    except:
        return name, None

def process_match(item):
    """Extracts data based on the JSON structure you provided."""
    m = item.get('match', {})
    if not m: return None
    
    # Check status - we want results, but can store live too
    status = m.get('matchstatus', 'unknown')
    res = m.get('result', {})
    
    return {
        'id': m.get('_id'),
        'teams': {
            'home': m['teams']['home']['name'],
            'away': m['teams']['away']['name']
        },
        'score': {
            'home': res.get('home', 0),
            'away': res.get('away', 0)
        },
        'status': status,
        'time': m.get('_dt', {}).get('time', 'N/A')
    }

def main():
    final_output = {}
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Fetch all sports in parallel (FAST)
        raw_responses = list(executor.map(lambda p: fetch_gismo(*p), SPORTS.items()))
        
    for name, data in raw_responses:
        if not data or 'doc' not in data:
            final_output[name] = []
            continue
            
        events = data['doc'][0].get('data', [])
        processed = [process_match(e) for e in events if process_match(e)]
        final_output[name] = processed

    # Save to your clean YAML (No quotes, easy for Lucra to read)
    with open("results.yaml", "w") as f:
        yaml.dump(final_output, f, default_flow_style=False, sort_keys=False)
    print("✅ YAML Updated successfully.")

if __name__ == "__main__":
    main()
