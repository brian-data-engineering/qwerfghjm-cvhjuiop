import requests
import yaml
from datetime import datetime

def run_sync():
    # Target URL
    u = "https://www.ke.sportpesa.com/api/results/search"
    
    h = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.ke.sportpesa.com/results"
    }

    try:
        # Fetching the data via POST
        r = requests.post(u, json={}, headers=h)
        r.raise_for_status()
        raw = r.json()
        
        processed = []
        for entry in raw:
            # Converting timestamp to readable format
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

        # Saving as metadata.yaml
        with open("metadata.yaml", "w") as f:
            yaml.dump(processed, f, default_flow_style=False, sort_keys=False)
            
        print(f"Sync complete. {len(processed)} items processed.")

    except Exception as e:
        print(f"Sync failed: {e}")

if __name__ == "__main__":
    run_sync()
