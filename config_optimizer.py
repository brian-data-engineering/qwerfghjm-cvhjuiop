import requests
import yaml
from datetime import datetime

def run_sync():
    u = "https://www.ke.sportpesa.com/api/results/search"
    
    h = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.ke.sportpesa.com/results",
        "X-Requested-With": "XMLHttpRequest"
    }

    # Adding a basic payload to trigger a real search
    # This mimics a user clicking "Search" on the results page
    payload = {
        "sportId": 0,    # 0 usually means "All Sports"
        "leagueId": 0,
        "today": True    # Focus on today's results
    }

    try:
        r = requests.post(u, json=payload, headers=h)
        r.raise_for_status()
        raw = r.json()
        
        # If the API returns a wrapper (like {"data": [...]}), we handle it
        results_list = raw if isinstance(raw, list) else raw.get('data', [])

        processed = []
        for entry in results_list:
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

        with open("metadata.yaml", "w") as f:
            yaml.dump(processed, f, default_flow_style=False, sort_keys=False)
            
        print(f"Processed {len(processed)} items.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_sync()
