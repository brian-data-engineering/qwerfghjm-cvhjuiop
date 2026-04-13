import requests
import yaml
from datetime import datetime

def run_sync():
    # 1. Setup the session and the exact endpoint
    session = requests.Session()
    u = "https://www.ke.sportpesa.com/api/results/search"
    
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.ke.sportpesa.com/results"
    }

    # 2. This is the "Key" that opens the door
    payload = {
        "sportId": 0, # 0 gets everything (Football, eFootball, Basketball)
        "today": True,
        "textSearch": ""
    }

    try:
        r = session.post(u, json=payload, headers=h)
        r.raise_for_status()
        raw_data = r.json()

        processed = []
        
        # 3. Loop through the exact data structure you provided
        for entry in raw_data:
            # We grab only the matches that actually have a result
            if entry.get("result"):
                # Convert the 'start_date' timestamp to readable time
                ms = entry.get('start_date', 0)
                dt = datetime.fromtimestamp(ms / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
                
                processed.append({
                    "game_id": entry.get("game_id"),
                    "sport": entry.get("sport_name"),
                    "league": entry.get("league"),
                    "match": f"{entry.get('team1')} vs {entry.get('team2')}",
                    "score": entry.get("result"),
                    "time": dt
                })

        # 4. Save to your stealth file
        with open("metadata.yaml", "w") as f:
            yaml.dump(processed, f, default_flow_style=False, sort_keys=False)
            
        print(f"Success! Captured {len(processed)} matches from the API.")

    except Exception as e:
        print(f"Sync failed: {e}")

if __name__ == "__main__":
    run_sync()
