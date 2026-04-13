import requests
import yaml
import time

def run_sync():
    # Use the exact endpoint
    url = "https://www.ke.sportpesa.com/api/results/search"
    
    # Generate today's midnight timestamp (matches your 1776027600)
    today_timestamp = int(time.time() // 86400 * 86400)

    # Added 'Host' and 'Origin' - these are often required by Kenyan APIs
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/json",
        "Origin": "https://www.ke.sportpesa.com",
        "Referer": "https://www.ke.sportpesa.com/results",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }

    payload = {
        "sportId": 0,
        "date": today_timestamp,
        "textSearch": "",
        "pagination": {
            "offset": 0,
            "limit": 100
        }
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        
        # Check if the response is actually valid before parsing JSON
        if not response.text:
            print(f"Error: Server sent an empty response. Status Code: {response.status_code}")
            return

        try:
            data = response.json()
        except Exception:
            print("Error: Server sent HTML instead of JSON. You might be blocked.")
            print(f"Response Preview: {response.text[:200]}")
            return

        # Handle both list and dict responses
        matches = data if isinstance(data, list) else data.get('data', [])

        processed = []
        for entry in matches:
            if entry.get("result"):
                processed.append({
                    "id": entry.get("game_id"),
                    "match": f"{entry.get('team1')} vs {entry.get('team2')}",
                    "score": entry.get("result"),
                    "sport": entry.get("sport_name"),
                    "league": entry.get("league")
                })

        with open("metadata.yaml", "w") as f:
            yaml.dump(processed, f, sort_keys=False)
            
        print(f"Success! Captured {len(processed)} items.")

    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    run_sync()
