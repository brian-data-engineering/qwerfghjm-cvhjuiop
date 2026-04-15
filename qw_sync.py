import os
import yaml
import requests
import re
from datetime import datetime

# Configuration
PARENT_IDS = ["70292228", "70292226"]
# This is the main URL that sets the session cookies
START_URL = "https://statshub.sportradar.com/betika/en/sport/1/tournament/406"
API_BASE = "https://sh.fn.sportradar.com/betika/en/Etc:UTC/gismo/stats_match_get/"

def get_token_manually():
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.betika.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,webp,*/*;q=0.8"
    }

    print("Attempting to handshake with Sportradar...")
    try:
        # Step 1: Visit the main page to get cookies
        response = session.get(START_URL, headers=headers, timeout=20)
        
        # Step 2: Look for the HMAC token in the page source
        # Sportradar often embeds the configuration or the first API call in a <script> tag
        html_content = response.text
        
        # Look for the pattern hmac= followed by alphanumeric characters
        match = re.search(r'hmac=([a-zA-Z0-9]+)', html_content)
        
        if match:
            token = f"hmac={match.group(1)}"
            print(f"Token found in page source: {token[:20]}...")
            return token, session
            
        # Step 3: If not in HTML, check if it's in a redirect URL
        if "hmac=" in response.url:
            token = response.url.split('?')[1]
            return token, session

    except Exception as e:
        print(f"Request error: {e}")
    
    return None, None

def main():
    token, session = get_token_manually()
    
    if not token:
        print("CRITICAL: Failed to acquire token via direct request.")
        # Create unique error log for the GitHub Web UI
        log_name = f"qw_fail_{datetime.now().strftime('%H%M%S')}.log"
        with open(log_name, "w") as f:
            f.write(f"Direct request blocked at {datetime.now()}")
        return

    for pid in PARENT_IDS:
        # Construct the specific API call
        target_url = f"{API_BASE}{pid}?{token}"
        
        try:
            # Reuse the session to keep cookies active
            res = session.get(target_url, timeout=15)
            if res.status_code == 200:
                data = res.json()
                if 'doc' in data and data['doc']:
                    match = data['doc'][0]['data']['match']
                    
                    qw_out = {
                        'id': pid,
                        'match': f"{match['teams']['home']['name']} vs {match['teams']['away']['name']}",
                        'result': f"{match['result']['home']}-{match['result']['away']}",
                        'status': match['status']['name'],
                        'scraped_at': datetime.now().isoformat()
                    }

                    filename = f"qw_{pid}.yml"
                    with open(filename, 'w') as f:
                        yaml.dump(qw_out, f)
                    print(f"Saved: {filename}")
        except Exception as e:
            print(f"Error on match {pid}: {e}")

if __name__ == "__main__":
    main()
