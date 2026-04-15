import os
import yaml
import requests
import re
from datetime import datetime

PARENT_IDS = ["70292228", "70292226"]
START_URL = "https://statshub.sportradar.com/betika/en/sport/1/tournament/406"
API_BASE = "https://sh.fn.sportradar.com/betika/en/Etc:UTC/gismo/stats_match_get/"

def get_token_manually():
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.betika.com/"
    }
    try:
        response = session.get(START_URL, headers=headers, timeout=20)
        match = re.search(r'hmac=([a-zA-Z0-9]+)', response.text)
        if match:
            return f"hmac={match.group(1)}", session
    except Exception as e:
        print(f"Handshake error: {e}")
    return None, None

def main():
    token, session = get_token_manually()
    if not token:
        print("CRITICAL: Token acquisition failed.")
        return

    print(f"Token active: {token[:15]}...")

    for pid in PARENT_IDS:
        target_url = f"{API_BASE}{pid}?{token}"
        try:
            res = session.get(target_url, timeout=15)
            if res.status_code == 200:
                json_data = res.json()
                
                # Dynamic extraction to avoid 'KeyError'
                # Path: doc[0] -> data -> match (sometimes wrapped)
                try:
                    doc = json_data.get('doc', [{}])[0]
                    data = doc.get('data', {})
                    
                    # If 'match' isn't at the root, it might be in 'match' key directly
                    match_obj = data.get('match')
                    
                    if match_obj:
                        home_team = match_obj['teams']['home']['name']
                        away_team = match_obj['teams']['away']['name']
                        home_score = match_obj['result'].get('home', 0)
                        away_score = match_obj['result'].get('away', 0)
                        
                        qw_out = {
                            'id': pid,
                            'teams': f"{home_team} vs {away_team}",
                            'score': f"{home_score}-{away_score}",
                            'status': match_obj.get('status', {}).get('name', 'Unknown'),
                            'scraped_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }

                        filename = f"qw_{pid}_{datetime.now().strftime('%H%M%S')}.yml"
                        with open(filename, 'w') as f:
                            yaml.dump(qw_out, f, default_flow_style=False)
                        print(f"Successfully saved: {filename}")
                    else:
                        print(f"Match ID {pid} data structure not found in response.")
                except Exception as parse_err:
                    print(f"Parsing error on {pid}: {parse_err}")
        except Exception as e:
            print(f"Network error on {pid}: {e}")

if __name__ == "__main__":
    main()
