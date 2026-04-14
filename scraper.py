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
    except Exception as e:
        print(f"Error fetching {name}: {e}")
        return name, None

def process_match(item):
    """Safely extracts data, ignoring non-dictionary items that cause crashes."""
    # FIX: Skip items that are strings (the cause of your AttributeError)
    if not isinstance(item, dict):
        return None
        
    m = item.get('match', {})
    if not isinstance(m, dict) or not m:
        return None
    
    status = m.get('matchstatus', 'unknown')
    res = m.get('result', {})
    teams = m.get('teams', {})
    
    # Nested safety for team names
    home_name = teams.get('home', {}).get('name', 'N/A')
    away_name = teams.get('away', {}).get('name', 'N/A')
    
    return {
        'id': m.get('_id'),
        'teams': {
            'home': home_name,
            'away': away_name
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
        raw_responses = list(executor.map(lambda p: fetch_gismo(*p), SPORTS.items()))
        
    for name, data in raw_responses:
        # Check if data exists and has the expected 'doc' list structure
        if not data or 'doc' not in data or not isinstance(data['doc'], list) or len(data['doc']) == 0:
            final_output[name] = []
            continue
            
        events = data['doc'][0].get('data', [])
        
        # Build processed list while filtering out None values
        processed = []
        if isinstance(events, list):
            for e in events:
                result = process_match(e)
                if result:
                    processed.append(result)
        
        final_output[name] = processed

    # Save to clean YAML - Perfect for Lucra's editable requirements
    with open("results.yaml", "w") as f:
        yaml.dump(final_output, f, default_flow_style=False, sort_keys=False)
    
    print("✅ YAML Updated successfully.")

if __name__ == "__main__":
    main()
