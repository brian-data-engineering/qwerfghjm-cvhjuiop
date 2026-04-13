import requests
import yaml
from datetime import datetime

def run_sync():
    # 1. The URL we found in the Network tab
    u = "https://www.ke.sportpesa.com/api/results/search"
    
    # 2. The "ID Card" (Headers) - Mimics your browser exactly
    h = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.ke.sportpesa.com/results",
        "X-Requested-With": "XMLHttpRequest"
    }

    # 3. The "Key" (Payload) - The specific search data
    payload = {
        "sportId": 0,
        "today": True,
        "textSearch": ""
    }

    try:
        # We send the request just like the Network tab does
        r = requests.post(u, json=payload, headers=h)
        r.raise_for_status()
        
        # The JSON output you saw in the browser
        raw_data = r.json()
        
        # Sportpesa data is often inside a list directly
        processed = []
        for entry in raw_data:
            # We only want it if it has a result (Arsenal 2:1 etc)
            if entry.get("result"):
                processed.append({
                    "uid": entry.get("game_id"),
                    "cat": entry.get("sport_name"),
                    "grp": entry.get("league"),
                    "val": f"{entry.get('team1')} vs {entry.get('team2')}",
                    "stat": entry.get("result"),
                    "ts": datetime.fromtimestamp(entry.get('start_date', 0) / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
                })

        # Save to your "stealth" file
        with open("metadata.yaml", "w") as f:
            yaml.dump(processed, f, default_flow_style=False, sort_keys=False)
            
        print(f"Success! Captured {len(processed)} matches.")

    except Exception as e:
        print(f"Failed to talk to the search endpoint: {e}")

if __name__ == "__main__":
    run_sync()
