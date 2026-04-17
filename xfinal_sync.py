import requests
import json
from datetime import datetime

def debug_vacuum(m_id):
    # THE EXACT URL YOU PROVIDED
    endpoint = "https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents"
    params = {
        "cfView": "3",
        "countEvents": "250",
        "country": "87",
        "gameId": str(m_id),
        "gr": "657",
        "grMode": "4",
        "lng": "en",
        "marketType": "1",
        "ref": "61"
    }
    
    # Matching the 'Incognito' look you confirmed works
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://1xbet.co.ke/en/line",
        "X-Requested-With": "XMLHttpRequest"
    }

    # Generate the full URL for the print statement
    prep = requests.Request('GET', endpoint, params=params).prepare()
    print(f"--- ATTEMPTING URL ---\n{prep.url}\n")

    try:
        resp = requests.get(endpoint, params=params, headers=headers, timeout=15)
        
        print(f"STATUS CODE: {resp.status_code}")
        
        if resp.status_code == 200:
            if not resp.text or resp.text.strip() == "":
                print("RESULT: 200 OK but BODY IS EMPTY (Server side hide)")
            else:
                data = resp.json()
                value = data.get("Value")
                if value:
                    print(f"SUCCESS: Found markets for Game {m_id}")
                    # Print first 500 chars of raw data to verify
                    print(f"RAW PREVIEW: {json.dumps(value)[:500]}...")
                else:
                    print("RESULT: 200 OK but 'Value' key is null/empty.")
        elif resp.status_code == 204:
            print("RESULT: 204 No Content (Match likely moved to Live or Finished)")
        else:
            print(f"RESULT: Failed with status {resp.status_code}")
            print(f"ERROR BODY: {resp.text}")

    except Exception as e:
        print(f"SCRIPT CRASHED: {e}")

if __name__ == "__main__":
    # Surgical strike on your specific ID
    debug_vacuum(324052436)
