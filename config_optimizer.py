import requests
import yaml
import time

def run_sync():
    # 1. API Endpoint & Timestamp
    url = "https://www.ke.sportpesa.com/api/results/search"
    today_timestamp = int(time.time() // 86400 * 86400)

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://www.ke.sportpesa.com",
        "Referer": "https://www.ke.sportpesa.com/results",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }

    # Increased limit to 500 to dig past the eFootball spam
    payload = {
        "sportId": 0,
        "date": today_timestamp,
        "textSearch": "",
        "pagination": {
            "offset": 0,
            "limit": 500 
        }
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        
        if not response.text:
            print("Error: Empty response")
            return

        data = response.json()
        matches = data if isinstance(data, list) else data.get('data', [])

        processed = []
        for entry in matches:
            sport = entry.get("sport_name", "")
            
            # --- THE BLOCKER ---
            # If the sport is NOT eFootball, we keep it. 
            # This keeps Football, Tennis, Basketball, etc.
            if sport != "eFootball":
                if entry.get("result"):
                    processed.append({
                        "id": entry.get("game_id"),
                        "match": f"{entry.get('team1')} vs {entry.get('team2')}",
                        "score": entry.get("result"),
                        "sport": sport,
                        "league": entry.get("league")
                    })

        # Overwrite metadata.yaml with the filtered results
        with open("metadata.yaml", "w") as f:
            yaml.dump(processed, f, sort_keys=False, default_flow_style=False)
            
        print(f"Sync Complete! Captured {len(processed)} real matches. eFootball excluded.")

    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    run_sync()
