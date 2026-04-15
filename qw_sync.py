import os
import yaml
import requests
import re
from datetime import datetime

PARENT_IDS = ["70292228", "70292226"]
# The tournament page you found earlier
TOURNAMENT_URL = "https://statshub.sportradar.com/betika/en/sport/1/tournament/406"
API_BASE = "https://sh.fn.sportradar.com/betika/en/Etc:UTC/gismo/stats_match_get/"

def scrape_lucra():
    # 1. Start a persistent session to hold cookies
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://statshub.sportradar.com/"
    })

    print("Step 1: Establishing session and fetching HMAC...")
    try:
        # We must visit the tournament page first to get the 'handshake'
        response = session.get(TOURNAMENT_URL, timeout=20)
        html = response.text
        
        # Regex to find the hmac
        token_match = re.search(r'hmac=([a-zA-Z0-9]+)', html)
        if not token_match:
            print("Failed to find HMAC in HTML. Site structure may have changed.")
            return
        
        token = f"hmac={token_match.group(1)}"
        print(f"Session established. Token: {token[:15]}...")

        # 2. Scrape each match ID using the validated session
        for pid in PARENT_IDS:
            target_url = f"{API_BASE}{pid}?{token}"
            
            # The API is strict: Referer must be the Statshub page
            api_headers = {
                "Referer": TOURNAMENT_URL
            }
            
            res = session.get(target_url, headers=api_headers, timeout=15)
            
            if res.status_code == 200:
                json_data = res.json()
                
                # Check for the exception you saw earlier
                doc = json_data.get('doc', [{}])[0]
                if doc.get('event') == 'exception':
                    print(f"Error for {pid}: {doc.get('data', {}).get('message')}")
                    continue

                # Navigate the JSON tree
                data = doc.get('data', {})
                match_obj = data.get('match')
                
                if match_obj:
                    home = match_obj['teams']['home']['name']
                    away = match_obj['teams']['away']['name']
                    h_score = match_obj['result'].get('home', 0)
                    a_score = match_obj['result'].get('away', 0)
                    
                    result = {
                        'id': pid,
                        'match': f"{home} vs {away}",
                        'score': f"{h_score}-{a_score}",
                        'status': match_obj.get('status', {}).get('name', 'Unknown'),
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }

                    filename = f"qw_{pid}.yml"
                    with open(filename, 'w') as f:
                        yaml.dump(result, f, default_flow_style=False)
                    print(f"Successfully scraped: {home} vs {away}")
                else:
                    print(f"Match data for {pid} not found in valid response.")
            else:
                print(f"HTTP {res.status_code} for match {pid}")

    except Exception as e:
        print(f"Scraper error: {e}")

if __name__ == "__main__":
    scrape_lucra()
