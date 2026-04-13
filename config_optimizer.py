import requests
import yaml
from datetime import datetime

def run_sync():
    # The API endpoint
    u = "https://www.ke.sportpesa.com/api/results/search"
    
    # Standard headers to look like a real browser
    h = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.ke.sportpesa.com/results",
        "X-Requested-With": "XMLHttpRequest"
    }

    # IMPORTANT: We add the filter here so the API actually returns data
    payload = {
        "sportId": 0,       # 0 = All Sports
        "today": True,      # Only today's results
        "textSearch": ""    # Leave empty to get everything for today
    }

    try:
        # Sending the POST request with the payload
        r = requests.post(u, json=payload, headers=h)
        r.raise_for_status()
        
        # Sportpesa usually returns a list or an object with a 'data' key
        raw_data = r.json()
        results = raw_data if isinstance(raw_data, list) else raw_data.get('data', [])
        
        processed = []
        for entry in results:
            # Check if there is actually a score/result
            if entry.get("result"):
                ms = entry.get('start_date', 0)
                dt = datetime.fromtimestamp(ms / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
                
                processed.append({
                    "uid": entry.get("game_id"),
                    "cat": entry.get("sport_name"),
                    "grp": entry.get("league"),
                    "val": f"{entry.get('team1')} vs {entry.get('team2')}",
                    "stat": entry.get("result"),
                    "ts": dt
                })

        # Save the results
        with open("metadata.yaml", "w") as f:
            yaml.dump(processed, f, default_flow_style=False, sort_keys=False)
            
        print(f"Success: Processed {len(processed)} matches.")

    except Exception as e:
        print(f"Sync failed: {e}")

if __name__ == "__main__":
    run_sync()
