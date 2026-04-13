import requests
import yaml
import time
import os
import re
from supabase import create_client

def run_sync():
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

    payload = {
        "sportId": 0,
        "date": today_timestamp,
        "textSearch": "",
        "pagination": {"offset": 0, "limit": 500} 
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if not response.text: return

        data = response.json()
        matches = data if isinstance(data, list) else data.get('data', [])

        processed_yaml = []
        supabase_batch = []

        for entry in matches:
            sport = entry.get("sport_name", "")
            raw_result = entry.get("result", "")

            # 1. Skip eFootball
            if sport == "eFootball" or not raw_result:
                continue

            # 2. Fundamental Scan Logic (Split Main vs Sub)
            if "canceled" in raw_result.lower():
                main_score, sub_score, status = "0:0", "", "canceled"
            elif "(" in raw_result:
                parts = re.split(r'\s*\(', raw_result.strip(')'))
                main_score = parts[0]
                sub_score = "(" + parts[1] + ")" if len(parts) > 1 else ""
                status = "completed"
            else:
                main_score, sub_score, status = raw_result, "", "completed"

            # 3. Data for YAML (Local File)
            processed_yaml.append({
                "id": entry.get("game_id"),
                "match": f"{entry.get('team1')} vs {entry.get('team2')}",
                "score": raw_result,
                "sport": sport,
                "league": entry.get("league")
            })

            # 4. Data for Supabase (Remote DB)
            supabase_batch.append({
                "game_id": str(entry.get("game_id")),
                "sport_type": sport,
                "match_name": f"{entry.get('team1')} vs {entry.get('team2')}",
                "main_score": main_score,
                "sub_scores": sub_score,
                "status": status,
                "league_name": entry.get("league"),
                "country_code": entry.get("iso_name")
            })

        # Save to YAML
        with open("metadata.yaml", "w") as f:
            yaml.dump(processed_yaml, f, sort_keys=False, default_flow_style=False)

        # Sync to Supabase
        sb_url = os.environ.get("SUPABASE_URL")
        sb_key = os.environ.get("SUPABASE_KEY")
        
        if sb_url and sb_key and supabase_batch:
            supabase = create_client(sb_url, sb_key)
            supabase.table("spresults").upsert(supabase_batch).execute()
            print(f"Success! {len(supabase_batch)} matches synced to Supabase.")

    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    run_sync()
