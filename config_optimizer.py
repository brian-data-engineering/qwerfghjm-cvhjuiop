import requests
import yaml
from datetime import datetime

def run_sync():
    # Use a Session object to handle cookies automatically
    session = requests.Session()
    
    # 1. "Visit" the main results page first to get a session cookie
    base_url = "https://www.ke.sportpesa.com/results"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    }
    session.get(base_url, headers=headers)

    # 2. Now talk to the Search API using that same session
    search_url = "https://www.ke.sportpesa.com/api/results/search"
    search_headers = {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.ke.sportpesa.com/results"
    }
    
    # Try a very specific payload
    payload = {
        "sportId": 0,
        "today": True
    }

    try:
        r = session.post(search_url, json=payload, headers=search_headers)
        data = r.json()
        
        # If data is still [], print the response to see why
        if not data:
            print("API returned empty list. Checking if Sportpesa has results for today...")

        processed = []
        for entry in data:
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
            
        print(f"Done. Captured {len(processed)} items.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_sync()
