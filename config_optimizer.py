import requests
import yaml
import time

def run_sync():
    url = "https://www.ke.sportpesa.com/api/results/search"
    
    # 1. Generate the exact timestamp for "Today" (Midnight)
    # This creates the 1776027600 value dynamically
    today_timestamp = int(time.time() // 86400 * 86400)

    headers = {
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.ke.sportpesa.com/results"
    }

    # 2. Use the timestamp in the payload
    payload = {
        "sportId": 0,
        "date": today_timestamp, # Send the 1776027600 value here
        "textSearch": "",
        "pagination": {
            "offset": 0,
            "limit": 100
        }
    }

    try:
        r = requests.post(url, json=payload, headers=headers)
        data = r.json()
        
        # In the snippet you shared, the list is the direct response
        matches = data if isinstance(data, list) else data.get('data', [])

        processed = []
        for entry in matches:
            if entry.get("result"):
                processed.append({
                    "id": entry.get("game_id"),
                    "match": f"{entry.get('team1')} vs {entry.get('team2')}",
                    "score": entry.get("result"),
                    "league": entry.get("league")
                })

        with open("metadata.yaml", "w") as f:
            yaml.dump(processed, f, sort_keys=False)
            
        print(f"Success! Captured {len(processed)} items using timestamp {today_timestamp}")

    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    run_sync()
