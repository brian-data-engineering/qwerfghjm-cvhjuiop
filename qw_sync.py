import os
import yaml
import requests
import re
import json
from datetime import datetime

# The tournament page containing the embedded JSON
TOURNAMENT_URL = "https://statshub.sportradar.com/betika/en/sport/1/tournament/406"
PARENT_IDS = ["70292228", "70292226"]

def scrape_lucra_inline():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,webp,*/*;q=0.8"
    })

    print("Step 1: Fetching tournament page HTML...")
    try:
        response = session.get(TOURNAMENT_URL, timeout=30)
        if response.status_code != 200:
            print(f"Failed to load page: HTTP {response.status_code}")
            return

        html = response.text
        
        # Step 2: Extract the 'window.DATA' or 'JSON' block from script tags
        # Sportradar usually stores data in a script tag as a JSON object
        print("Step 2: Searching for embedded JSON data...")
        
        # This regex looks for common patterns where Sportradar hides its match data in HTML
        # Usually it's inside a JSON.parse() or a variable definition
        json_pattern = r'JSON\.parse\(\"(.*?)\"\)'
        found_data = re.search(json_pattern, html)
        
        if not found_data:
            # Fallback: Look for the raw match ID inside the HTML text
            print("Direct JSON block not found. Searching for match IDs in raw text...")
            for pid in PARENT_IDS:
                if pid in html:
                    print(f"Found Match ID {pid} in page source, but data is obfuscated.")
            return

        # Decode the escaped JSON string
        raw_json_str = found_data.group(1).encode().decode('unicode_escape')
        full_data = json.loads(raw_json_str)
        
        # Step 3: Loop through match IDs and extract from the big data object
        # The structure is usually: full_data -> doc -> data -> matches
        for pid in PARENT_IDS:
            match_found = False
            
            # We look through the 'doc' list for any 'match' that matches our ID
            for doc in full_data.get('doc', []):
                matches = doc.get('data', {}).get('matches', [])
                if not matches: # Sometimes it's nested differently
                    matches = [doc.get('data', {}).get('match', {})]

                for m in matches:
                    if str(m.get('_id')) == pid or str(m.get('id')) == pid:
                        home = m['teams']['home']['name']
                        away = m['teams']['away']['name']
                        score = f"{m['result'].get('home', 0)}-{m['result'].get('away', 0)}"
                        
                        qw_out = {
                            'id': pid,
                            'teams': f"{home} vs {away}",
                            'score': score,
                            'status': m.get('status', {}).get('name', 'Live'),
                            'scraped_at': datetime.now().isoformat()
                        }
                        
                        filename = f"qw_{pid}.yml"
                        with open(filename, 'w') as f:
                            yaml.dump(qw_out, f, default_flow_style=False)
                        print(f"Successfully extracted: {home} vs {away}")
                        match_found = True
                        break
            
            if not match_found:
                print(f"Match ID {pid} not found in the page's current data block.")

    except Exception as e:
        print(f"Extraction Error: {e}")

if __name__ == "__main__":
    scrape_lucra_inline()
