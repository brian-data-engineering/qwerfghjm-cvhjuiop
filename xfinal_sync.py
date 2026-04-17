import requests
from supabase import create_client

# Your match details
m_id = 710135735
d_id = 320958746

# 1. Fetch the data (The URL from your browser)
url = f"https://1xbet.co.ke/service-api/main-line-feed/v1/gameEvents?gameId={d_id}&lng=en&marketType=1"
data = requests.get(url).json()

# 2. Extract and Loop
sub_games = data.get('subGamesForMainGame', [])

for sub in sub_games:
    period_name = sub.get('periodName', 'Full Time')
    event_groups = sub.get('eventGroups', [])
    
    # 3. Insert into Supabase
    for group in event_groups:
        supabase.table("xmatch_odds_deep").insert({
            "match_id": m_id,
            "sub_id": sub.get('id'),
            "period": period_name,
            "group_id": group.get('groupId'),
            "raw_data": group, # This saves the JSON object for that specific market
            "scraped_at": "now()"
        }).execute()

print(f"Deep sync complete for match {m_id}")
