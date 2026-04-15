import os
import yaml
import requests
import re
from datetime import datetime

PARENT_IDS = ["70292228", "70292226"]
START_URL = "https://statshub.sportradar.com/betika/en/sport/1/tournament/406"
API_BASE = "https://sh.fn.sportradar.com/betika/en/Etc:UTC/gismo/stats_match_get/"

def get_token_manually():
    session = requests.Session()
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Referer": "https://www.betika.com/"}
    try:
        response = session.get(START_URL, headers=headers, timeout=20)
        match = re.search(r'hmac=([a-zA-Z0-9]+)', response.text)
        if match:
            return f"hmac={match.group(1)}", session
    except Exception as e:
        print(f"Handshake error: {e}")
    return None, None

def main():
    token, session = get_token_manually()
    if not token:
        print("CRITICAL: Token acquisition failed.")
        return

    for pid in PARENT_IDS:
        target_url = f"{API_BASE}{pid}?{token}"
        try:
            res = session.get(target_url, timeout=15)
            if res.status_code == 200:
                raw_text = res.text
                # --- DEBUG LOGGING ---
                print(f"\n--- RAW DATA FOR ID {pid} ---")
                print(raw_text[:800]) # This shows us the structure
                print("--- END RAW DATA ---\n")
                # ---------------------
        except Exception as e:
            print(f"Network error on {pid}: {e}")

if __name__ == "__main__":
    main()
