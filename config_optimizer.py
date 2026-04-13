import requests
import yaml
from datetime import datetime

def run_sync():
    # 1. The 'Kitchen Door' URL
    url = "https://www.ke.sportpesa.com/api/results/search"
    
    # 2. The 'ID Card' (Headers)
    # This tells the server we are a real browser, not a simple script
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.ke.sportpesa.com/results"
    }

    # 3. The 'Key' (Payload)
    # We send the exact filters the 'Search' button uses
    payload = {
        "sportId": 0,    # 0 fetches all sports
        "today": True,
        "textSearch": ""
    }

    try:
        # Use POST to avoid the 405 error
        response = requests.post(url, json=payload, headers=headers)
        
        # Check if we got a 200 OK
        if response.status_code != 200:
            print(f"Failed! Server returned status: {response.status_code}")
            return

        raw_data = response.json()
        processed = []

        # 4. Data Extraction Logic
        # Based on the structure you found in the Network tab
        for entry in raw_data:
            # Only save matches that have a result (e.g., '2:1')
            if entry.get("result"):
                # Convert the 'start_date' timestamp (milliseconds) to readable format
                ms = entry.get('start_date', 0)
                readable_time = datetime.fromtimestamp(ms / 1000.0).strftime('%Y-%m-%d %H:%M:%S')
                
                processed.append({
                    "id": entry.get("game_id"),
                    "sport": entry.get("sport_name"),
                    "league": entry.get("league"),
                    "match": f"{entry.get('team1')} vs {entry.get('team2')}",
                    "score": entry.get("result"),
                    "date": readable_time
                })

        # 5. Save to your Lucra project file
        with open("metadata.yaml", "w") as f:
            yaml.dump(processed, f, default_flow_style=False, sort_keys=False)
            
        print(f"Success! Captured {len(processed)} matches.")

    except Exception as e:
        print(f"Critical Error: {e}")

if __name__ == "__main__":
    run_sync()
