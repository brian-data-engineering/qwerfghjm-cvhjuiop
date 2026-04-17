import requests

def test_url_only():
    url = "https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents"
    params = {
        "cfView": "3", "countEvents": "250", "country": "87",
        "gameId": "324052436", "gr": "657", "grMode": "4",
        "lng": "en", "marketType": "1", "ref": "61"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://1xbet.co.ke/en/line"
    }

    print("Requesting 1xBet API...")
    resp = requests.get(url, params=params, headers=headers)
    
    if resp.status_code == 200:
        data = resp.json()
        # Navigate to the events
        value = data.get("Value", {})
        sub_games = value.get("subGamesForMainGame", [])
        
        if sub_games:
            print(f"SUCCESS! Found {len(sub_games)} sub-games.")
            # Print the first sub-game name as a test
            print(f"First market group found: {sub_games[0].get('subGameName')}")
        else:
            print("Connected, but 'subGamesForMainGame' is empty. The match might have ended.")
    else:
        print(f"Failed with status: {resp.status_code}")

if __name__ == "__main__":
    test_url_only()
