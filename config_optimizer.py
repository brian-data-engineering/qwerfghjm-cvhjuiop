import requests
import yaml
from datetime import datetime

def run_sync():
    session = requests.Session()
    
    # 1. Headers to look like a very standard browser
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.ke.sportpesa.com/results"
    }

    u = "https://www.ke.sportpesa.com/api/results/search"
    payload = {"sportId": 0, "today": True}

    try:
        r = session.post(u, json=payload, headers=h)
        
        # DEBUG: Let's see what we actually got
        print(f"Status Code: {r.status_code}")
        
        if r.status_code != 200:
            print("Server returned an error. We might be blocked.")
            return

        # Attempt to parse JSON safely
        try:
            raw_data = r.json()
        except Exception:
            print("Failed to parse JSON. Server returned this instead:")
            print(r.text[:500]) # Print first 500 chars of the error
            return

        processed = []
        for entry in raw_data:
            if entry.get("result"):
                processed.append({
                    "uid": entry.get("game_id"),
                    "cat": entry.get("sport_name"),
                    "val": f"{entry.get('team1')} vs {entry.get('team2')}",
                    "stat": entry.get("result"),
                    "ts": datetime.fromtimestamp(entry.get('start_date', 0) / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
                })

        with open("metadata.yaml", "w") as f:
            yaml.dump(processed, f, default_flow_style=False, sort_keys=False)
            
        print(f"Captured {len(processed)} items.")

    except Exception as e:
        print(f"Script Error: {e}")

if __name__ == "__main__":
    run_sync()
